import frappe

def run():
    doc = frappe.get_doc("DocType", "Glific Flow")
    doc.custom = 0
    doc.save(ignore_permissions=True)
    frappe.db.commit()
    print("Glific Flow DocType is now standard")

