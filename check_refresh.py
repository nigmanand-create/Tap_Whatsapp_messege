import frappe
frappe.init(site="tapbuddy.local")
frappe.connect()
settings = frappe.get_single("TAP Buddy Settings")
print("refresh_token:", settings.get_password("glific_refresh_token"))
