import frappe

def run():
    print("Creating WhatsApp Group Collection...")
    if not frappe.db.exists("DocType", "WhatsApp Group Collection"):
        doc = frappe.get_doc({
            "doctype": "DocType",
            "name": "WhatsApp Group Collection",
            "module": "TAP Buddy",
            "custom": 0,
            "fields": [
                {
                    "fieldname": "glific_collection_id",
                    "fieldtype": "Data",
                    "label": "Glific Collection ID",
                    "unique": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "collection_name",
                    "fieldtype": "Data",
                    "label": "Collection Name",
                    "in_list_view": 1,
                    "reqd": 1
                }
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        doc.insert(ignore_permissions=True)
        print("Created WhatsApp Group Collection")
    else:
        print("WhatsApp Group Collection already exists")

    print("Creating WhatsApp Group Collection Mapping...")
    if not frappe.db.exists("DocType", "WhatsApp Group Collection Mapping"):
        doc2 = frappe.get_doc({
            "doctype": "DocType",
            "name": "WhatsApp Group Collection Mapping",
            "module": "TAP Buddy",
            "custom": 0,
            "fields": [
                {
                    "fieldname": "collection",
                    "fieldtype": "Link",
                    "options": "WhatsApp Group Collection",
                    "label": "Collection",
                    "reqd": 1,
                    "in_list_view": 1
                },
                {
                    "fieldname": "whatsapp_group",
                    "fieldtype": "Link",
                    "options": "WhatsApp Group",
                    "label": "WhatsApp Group",
                    "reqd": 1,
                    "in_list_view": 1
                }
            ],
            "permissions": [{"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}]
        })
        doc2.insert(ignore_permissions=True)
        print("Created WhatsApp Group Collection Mapping")
    else:
        print("WhatsApp Group Collection Mapping already exists")
        
    frappe.db.commit()
    print("Done")

