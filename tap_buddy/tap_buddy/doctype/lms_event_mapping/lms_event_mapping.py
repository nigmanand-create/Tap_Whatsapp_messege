import frappe
from frappe.model.document import Document


class LMSEventMapping(Document):
    def validate(self):
        if self.action == "Create Campaign":
            if not self.template:
                frappe.throw("WhatsApp Template is required when action is Create Campaign.")

            if self.targeting_type not in ("Single School", "School Group"):
                frappe.throw("Targeting type must be Single School or School Group.")
