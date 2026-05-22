import frappe
from frappe.model.document import Document


class GlificContactGroupMapping(Document):
    def validate(self):
        if not self.school_group:
            frappe.throw("School Group is required.")

        if not self.glific_group_id:
            frappe.throw("Glific Group ID is required.")
