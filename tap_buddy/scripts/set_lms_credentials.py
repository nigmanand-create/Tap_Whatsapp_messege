import frappe

def run():
    print("Setting LMS credentials...")
    settings = frappe.get_single("LMS Integration Settings")
    settings.lms_username = "manu.aguest@theapprenticeproject.org"
    settings.lms_password = "Tap@123"
    settings.lms_base_url = "https://lms.evalix.xyz"
    settings.save(ignore_permissions=True)
    frappe.db.commit()
    print("✅ Credentials saved successfully!")
