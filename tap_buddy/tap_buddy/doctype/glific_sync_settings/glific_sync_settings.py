import frappe
from frappe.model.document import Document


class GlificSyncSettings(Document):
    def validate(self):
        if self.enabled and not (self.sync_contacts or self.sync_groups):
            frappe.throw("Enable at least one sync option (contacts or groups).")

        if self.batch_size is not None:
            if self.batch_size < 1 or self.batch_size > 1000:
                frappe.throw("Batch size must be between 1 and 1000.")

        if self.enabled and not self.dry_run:
            settings = frappe.get_single("TAP Buddy Settings")
            if not settings.glific_url or not settings.glific_token:
                frappe.throw("Configure Glific URL and Token in TAP Buddy Settings before enabling sync.")

        if self.sync_groups:
            mapping_exists = frappe.get_all(
                "Glific Contact Group Mapping",
                filters={"enabled": 1},
                fields=["name"],
                limit=1,
            )
            if not mapping_exists:
                frappe.throw("Add at least one enabled Glific Contact Group Mapping before syncing groups.")
