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

        # Check Campaign Type Requirements
        campaign_type = getattr(self, "campaign_type", "Template")
        if campaign_type == "Template":
            if not getattr(self, "template", None):
                frappe.throw("WhatsApp Template is required")
            self._sync_message_template()
        elif campaign_type == "Flow":
            if not getattr(self, "glific_flow", None):
                frappe.throw("Glific Flow is required")

        # Check Send Date
        if not getattr(self, "send_date", None):
            frappe.throw("Send Date is required")

    def on_submit(self):
        # Queue-first: submit only enqueues, dispatch builds recipients/logs
        settings = frappe.get_single("TAP Buddy Settings")
        
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
                timeout=3600,
                job_id=f"dispatch_campaign_{self.name}",
                deduplicate=True,
                enqueue_after_commit=True
            )

        # Update Campaign Status (Queued is canonical; Scheduled is transitional)
        self.db_set("status", STATUS_QUEUED)

        # By default we follow a queue-first architecture: recipient creation
        # happens in the dispatcher to avoid synchronous work during submit.
        # For backward-compatibility or debugging, admins can enable
        # `create_recipients_on_submit` in TAP Buddy Settings to opt-in to
        # immediate recipient creation.
        try:
            create_now = getattr(settings, "create_recipients_on_submit", 0)
            if create_now:
                from tap_buddy.services.recipients import build_campaign_recipients

                created = build_campaign_recipients(self.name)
                frappe.logger().info(f"Created {created} campaign recipients for {self.name} on submit")
        except Exception:
            frappe.logger().exception("Error creating campaign recipients on submit")

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

        self.message_template = template_text