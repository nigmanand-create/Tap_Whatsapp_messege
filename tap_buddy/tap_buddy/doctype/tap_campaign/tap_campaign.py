import frappe
from frappe.model.document import Document

from tap_buddy.utils.constants import STATUS_QUEUED
from typing import TYPE_CHECKING

class TAPCampaign(Document):
    if TYPE_CHECKING:
        campaign_name: str
        school_name: str | None
        template: str
        message_template: str
        send_date: str
        status: str
        targeting_type: str
        school_group: str | None
        total_recipients: int
        sent_count: int
        delivered_count: int
        failed_count: int


    def validate(self):
        targeting_type = self.targeting_type or "Single School"
        if targeting_type == "Single School" and not self.school_name:
            frappe.throw("School is required")

        if targeting_type == "School Group" and not self.school_group:
            frappe.throw("School Group is required")

        # Check Template
        if not self.template:
            frappe.throw("WhatsApp Template is required")

        # Check Send Date
        if not self.send_date:
            frappe.throw("Send Date is required")

        self._sync_message_template()


    def before_submit(self):
        self.status = STATUS_QUEUED


    def on_submit(self):
        # Queue-first: submit only enqueues, dispatch builds recipients/logs
        settings = frappe.get_single("TAP Buddy Settings")
        try:
            from tap_buddy.services.recipients import build_campaign_recipients

            build_campaign_recipients(self.name)
        except Exception:
            frappe.logger().exception("Error creating campaign recipients on submit")
        
        if settings.sync_mode_fallback:
            # Synchronous execution (Debugging only)
            frappe.logger().warning("Executing campaign synchronously due to sync_mode_fallback")
            from tap_buddy.tasks.scheduler import dispatch_campaign
            dispatch_campaign(self.name)
        else:
            # Default Queue Execution
            frappe.enqueue(
                "tap_buddy.tasks.scheduler.dispatch_campaign",
                campaign_name=self.name,
                queue="default",
                timeout=3600
            )

    def on_cancel(self):
        # Cleanup logic if a scheduled campaign is canceled
        frappe.db.set_value("TAP Campaign", self.name, "status", "Cancelled")

    def _sync_message_template(self):
        if not self.template:
            return

        template_text = frappe.get_value("WhatsApp Template", self.template, "message")
        if not template_text:
            template_text = frappe.get_value("WhatsApp Template", self.template, "message_body")
        if not template_text:
            return

        if not self.message_template:
            self.message_template = template_text
            return

        previous = self.get_doc_before_save()
        if not previous or previous.template == self.template:
            return

        old_template = frappe.get_value("WhatsApp Template", previous.template, "message")
        if not old_template:
            old_template = frappe.get_value("WhatsApp Template", previous.template, "message_body")

        if (self.message_template or "").strip() == (old_template or "").strip():
            self.message_template = template_text
        else:
            frappe.msgprint(
                "Template changed, but Message Template was customized. Keeping your custom content."
            )