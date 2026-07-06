# -*- coding: utf-8 -*-
import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime
from datetime import datetime

class RecurringCampaignTemplate(Document):
    def validate(self):
        self.validate_dates()
        self.validate_targeting()
        self.validate_campaign_type()
        self.validate_cron()

    def validate_dates(self):
        if not self.start_date:
            frappe.throw("Start Date & Time is required.")
        if self.end_date:
            if get_datetime(self.end_date) <= get_datetime(self.start_date):
                frappe.throw("Optional End Date must be strictly after Start Date & Time.")

    def validate_targeting(self):
        targeting_type = self.targeting_type or "Single School"
        if targeting_type == "Single School" and not self.school_name:
            frappe.throw("School is required for Single School targeting.")
        elif targeting_type == "School Group" and not self.school_group:
            frappe.throw("School Group is required for School Group targeting.")
        elif targeting_type == "WhatsApp Group" and not self.target_group:
            frappe.throw("WhatsApp Group is required for WhatsApp Group targeting.")
        elif targeting_type == "WhatsApp Group Collection" and not self.target_collection:
            frappe.throw("WhatsApp Group Collection is required for WhatsApp Group Collection targeting.")

    def validate_campaign_type(self):
        campaign_type = self.campaign_type or "Flow"
        if campaign_type == "Template" and not self.template:
            frappe.throw("WhatsApp Template is required when Campaign Type is Template.")
        elif campaign_type == "Flow" and not self.glific_flow:
            frappe.throw("Glific Flow is required when Campaign Type is Flow.")

    def validate_cron(self):
        if self.recurrence_type == "Custom Cron":
            if not self.cron_expression:
                frappe.throw("Custom Cron Expression is required when Recurrence Type is Custom Cron.")
            try:
                from croniter import croniter
                if not croniter.is_valid(self.cron_expression):
                    frappe.throw(f"Invalid cron expression: {self.cron_expression}")
            except ImportError:
                # If croniter is not installed, perform basic 5-part split check
                parts = self.cron_expression.strip().split()
                if len(parts) != 5:
                    frappe.throw(f"Invalid cron expression format (must have 5 fields): {self.cron_expression}")

    def format_campaign_name(self, target_dt: datetime = None) -> str:
        """Helper to generate formatted campaign name based on naming_pattern."""
        dt = target_dt or datetime.utcnow()
        pattern = self.naming_pattern or "{template_name} - {YYYY}-{MM}-{DD}"
        
        month_names = ["January", "February", "March", "April", "May", "June", 
                       "July", "August", "September", "October", "November", "December"]
        
        name = pattern.replace("{template_name}", str(self.template_name))
        name = name.replace("{YYYY}", dt.strftime("%Y"))
        name = name.replace("{MM}", dt.strftime("%m"))
        name = name.replace("{DD}", dt.strftime("%d"))
        week_num = int(dt.strftime("%W"))
        name = name.replace("{WW}", f"{week_num:02d}")
        name = name.replace("{W}", str(week_num))
        m_name = month_names[dt.month - 1]
        name = name.replace("{MMMM}", m_name)
        name = name.replace("{Month}", m_name)
        return name
