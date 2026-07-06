# -*- coding: utf-8 -*-
"""
Campaign Generation Service
===========================
Phase 3 Implementation: Receives an execution plan or scheduled window from a
Recurring Campaign Template and creates an independent, transactional TAP Campaign
compatible with the existing trigger_scheduled_campaigns() scheduler.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union
import frappe
from frappe.utils import get_datetime, now_datetime

from tap_buddy.tasks.recurring import compute_idempotency_key, is_window_executed


class CampaignGenerationService:
    """
    Service responsible for generating independent TAP Campaigns from execution plans.
    Guarantees idempotency, transaction boundaries with rollback, and strict naming patterns.
    """

    @classmethod
    def format_campaign_name(cls, template_doc: Any, target_dt: datetime) -> str:
        """
        Formats the generated campaign name according to the template's naming_pattern.
        Supports {template_name}, {YYYY}, {MM}, {DD}, {WW}, {W}, {MMMM}, and {Month}.
        """
        pattern = getattr(template_doc, "naming_pattern", None) or "{template_name} - {YYYY}-{MM}-{DD}"
        t_name = getattr(template_doc, "template_name", None) or getattr(template_doc, "name", "Campaign")

        month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]

        name = pattern.replace("{template_name}", str(t_name))
        name = name.replace("{YYYY}", target_dt.strftime("%Y"))
        name = name.replace("{MM}", target_dt.strftime("%m"))
        name = name.replace("{DD}", target_dt.strftime("%d"))

        week_num = int(target_dt.strftime("%W"))
        name = name.replace("{WW}", f"{week_num:02d}")
        name = name.replace("{W}", str(week_num))

        m_name = month_names[target_dt.month - 1]
        name = name.replace("{MMMM}", m_name)
        name = name.replace("{Month}", m_name)

        return name

    @classmethod
    def generate_campaign(
        cls,
        template_doc: Any,
        scheduled_time: Union[datetime, str],
        idempotency_key: Optional[str] = None
    ) -> Optional[str]:
        """
        Generates a single brand-new TAP Campaign for a scheduled execution window.
        Wraps creation and history linking inside an atomic rollback boundary.
        """
        scheduled_dt = get_datetime(scheduled_time)
        t_name = getattr(template_doc, "template_name", None) or getattr(template_doc, "name", "Template")

        if not idempotency_key:
            idempotency_key = compute_idempotency_key(t_name, scheduled_dt)

        # Requirement 7: Prevent duplicate campaign generation
        if is_window_executed(idempotency_key):
            frappe.logger("recurring").info(
                f"[CAMPAIGN GEN] Idempotency key {idempotency_key} already executed. Skipping."
            )
            existing = frappe.db.get_value("Generated Campaign History", {"idempotency_key": idempotency_key}, "campaign")
            return existing

        try:
            if hasattr(frappe.db, "savepoint"):
                frappe.db.savepoint("generate_campaign_sp")

            formatted_name = cls.format_campaign_name(template_doc, scheduled_dt)

            new_campaign = frappe.new_doc("TAP Campaign")
            new_campaign.campaign_name = formatted_name
            new_campaign.campaign_type = getattr(template_doc, "campaign_type", "Flow")
            new_campaign.template = getattr(template_doc, "template", None)
            new_campaign.glific_flow = getattr(template_doc, "glific_flow", None)
            new_campaign.targeting_type = getattr(template_doc, "targeting_type", "Single School")
            new_campaign.school_name = getattr(template_doc, "school_name", None)
            new_campaign.school_group = getattr(template_doc, "school_group", None)
            new_campaign.target_group = getattr(template_doc, "target_group", None)
            new_campaign.target_collection = getattr(template_doc, "target_collection", None)
            new_campaign.send_date = scheduled_dt.strftime("%Y-%m-%d %H:%M:%S")
            
            # Requirement 9: Compatible immediately with trigger_scheduled_campaigns()
            new_campaign.status = "Scheduled"

            # Requirement 3: Analytics isolation
            new_campaign.total_recipients = 0
            new_campaign.sent_count = 0
            new_campaign.delivered_count = 0
            new_campaign.failed_count = 0

            # Copy variable mappings
            if hasattr(template_doc, "variable_mappings") and template_doc.variable_mappings:
                for vm in template_doc.variable_mappings:
                    new_campaign.append("variable_mappings", {
                        "variable_name": getattr(vm, "variable_name", None),
                        "mapping_type": getattr(vm, "mapping_type", None),
                        "static_value": getattr(vm, "static_value", None),
                        "contact_field": getattr(vm, "contact_field", None),
                    })

            new_campaign.insert(ignore_permissions=True)

            # Requirement 4: Store the relationship in Generated Campaign History
            history_row = frappe.new_doc("Generated Campaign History")
            history_row.parent = template_doc.name
            history_row.parenttype = "Recurring Campaign Template"
            history_row.parentfield = "generated_campaigns"
            history_row.campaign = new_campaign.name
            history_row.generated_at = now_datetime()
            history_row.scheduled_send_time = scheduled_dt.strftime("%Y-%m-%d %H:%M:%S")
            history_row.status = "Generated"
            history_row.idempotency_key = idempotency_key
            history_row.sent_count = 0
            history_row.delivered_count = 0
            history_row.read_count = 0
            history_row.failed_count = 0
            history_row.insert(ignore_permissions=True)

            frappe.logger("recurring").info(
                f"[CAMPAIGN GEN] Successfully generated campaign '{new_campaign.name}' for key {idempotency_key}"
            )
            return new_campaign.name

        except Exception as e:
            if hasattr(frappe.db, "rollback"):
                frappe.db.rollback()

            err_str = str(e)
            dup_exc = getattr(frappe.exceptions, "DuplicateEntryError", tuple()) if hasattr(frappe, "exceptions") else tuple()
            is_dup = (isinstance(e, dup_exc) if isinstance(dup_exc, type) else False) or "Duplicate entry" in err_str or "1062" in err_str or "Unique" in err_str

            if is_dup:
                frappe.logger("recurring").info(
                    f"[CAMPAIGN GEN] Duplicate key violation caught for {idempotency_key}. Treating as successful no-op."
                )
                existing = frappe.db.get_value("Generated Campaign History", {"idempotency_key": idempotency_key}, "campaign")
                return existing

            frappe.logger("recurring").error(
                f"[CAMPAIGN GEN FAILED] Transaction rolled back for template '{t_name}': {e}"
            )
            raise

    @classmethod
    def generate_from_plan(
        cls,
        template_doc: Any,
        execution_plan: Dict[str, Any]
    ) -> List[str]:
        """
        Receives a validated execution plan produced by Phase 2 and generates
        independent TAP Campaigns for each window in planned_windows.
        Requirement 5: If creation fails, marks execution plan as failed so
        the template does NOT advance to the next execution.
        """
        planned_windows = execution_plan.get("planned_windows", [])
        created_campaigns = []

        for win_str in planned_windows:
            win_dt = get_datetime(win_str)
            t_name = getattr(template_doc, "template_name", None) or getattr(template_doc, "name", "Template")
            idempotency_key = compute_idempotency_key(t_name, win_dt)
            try:
                c_name = cls.generate_campaign(template_doc, win_dt, idempotency_key=idempotency_key)
                if c_name:
                    created_campaigns.append(c_name)
            except Exception as e:
                execution_plan["status"] = "FAILED"
                execution_plan["error"] = str(e)
                raise

        return created_campaigns
