import re
import frappe
from frappe.model.document import Document


class WhatsAppTemplate(Document):
    def validate(self):
        """Auto-detect Mustache-like params in `message` and store them in `detected_params`."""
        msg = (self.message or "")
        params = re.findall(r'{{\s*([^}]+?)\s*}}', msg)
        if params:
            # store as comma-separated list
            self.detected_params = ",".join([p.strip() for p in params])
        else:
            self.detected_params = ""