import frappe

def execute():
    frappe.init(site="tapbuddy.local")
    frappe.connect()
    try:
        doc = frappe.get_single("TAP Buddy Settings")
        token = doc.get_password("glific_token")
        print(f"ACTUAL_TOKEN=[{token}]")
    finally:
        frappe.destroy()
