import frappe
from frappe.model.document import Document


class LMSIntegrationSettings(Document):
    def validate(self):
        if self.enabled:
            if not self.webhook_secret:
                frappe.throw("Webhook secret is required when LMS integration is enabled.")

            if self.webhook_signature_header and " " in self.webhook_signature_header:
                frappe.throw("Webhook signature header cannot contain spaces.")

        if self.polling_enabled:
            if not self.lms_base_url:
                frappe.throw("LMS base URL is required when polling is enabled.")
            if not self.lms_api_key:
                frappe.throw("LMS API key is required when polling is enabled.")
            if not (self.lms_base_url.startswith("http://") or self.lms_base_url.startswith("https://")):
                frappe.throw("LMS base URL must start with http:// or https://")

        if self.polling_interval_minutes and self.polling_interval_minutes < 5:
            frappe.throw("Polling interval must be at least 5 minutes.")
