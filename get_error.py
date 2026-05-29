import frappe
frappe.init(site="tapbuddy.local")
frappe.connect()
errors = frappe.get_all("Error Log", fields=["error"], limit=1, order_by="creation desc")
print(errors[0].error if errors else "No errors")
