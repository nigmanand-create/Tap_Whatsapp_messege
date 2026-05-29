import frappe
frappe.init(site="tapbuddy.local")
frappe.connect()
auths = frappe.db.sql("SELECT fieldname FROM __Auth WHERE doctype='TAP Buddy Settings'", as_dict=True)
print(auths)
