import frappe
from frappe.model.document import Document


class GlificFieldMapping(Document):
    def validate(self):
        if self.source_doctype != "School":
            frappe.throw("Only School is supported as a source DocType for Glific sync.")

        if self.source_field:
            meta = frappe.get_meta("School")
            if not meta.get_field(self.source_field):
                frappe.throw(f"Unknown School field: {self.source_field}")
