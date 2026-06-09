import frappe

def run():
    if frappe.db.exists("DocType", "Glific Flow"):
        print("Glific Flow DocType already exists")
        return
        
    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": "Glific Flow",
        "module": "TAP Buddy",
        "custom": 1,
        "is_submittable": 0,
        "fields": [
            {
                "fieldname": "flow_id",
                "label": "Flow ID",
                "fieldtype": "Data",
                "reqd": 1,
                "unique": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "flow_name",
                "label": "Flow Name",
                "fieldtype": "Data",
                "reqd": 1,
                "in_list_view": 1
            },
            {
                "fieldname": "flow_type",
                "label": "Flow Type",
                "fieldtype": "Data",
                "in_list_view": 1
            },
            {
                "fieldname": "is_active",
                "label": "Is Active",
                "fieldtype": "Check",
                "in_list_view": 1
            },
            {
                "fieldname": "is_background",
                "label": "Is Background",
                "fieldtype": "Check"
            }
        ],
        "permissions": [
            {
                "role": "System Manager",
                "read": 1,
                "write": 1,
                "create": 1,
                "delete": 1
            }
        ],
        "naming_rule": "By fieldname",
        "autoname": "field:flow_id",
        "title_field": "flow_name",
        "search_fields": "flow_name,flow_id",
        "sort_field": "flow_name",
        "sort_order": "ASC"
    })
    
    doc.insert(ignore_permissions=True)
    frappe.db.commit()
    print("Glific Flow DocType created successfully")

