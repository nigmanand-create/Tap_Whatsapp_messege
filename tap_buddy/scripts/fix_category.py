import frappe

def fix_category():
    doc = frappe.get_doc('DocType', 'WhatsApp Template')
    for field in doc.fields:
        if field.fieldname == 'category':
            field.fieldtype = "Data"
            field.options = ""
            break
    doc.save(ignore_permissions=True)
    print("Fixed category fieldtype to Data.")

if __name__ == "__main__":
    fix_category()
