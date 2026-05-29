import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

def create_doctype():
    frappe.init(site="tapbuddy.local")
    frappe.connect()

    if frappe.db.exists("DocType", "Glific Auth Log"):
        print("Glific Auth Log already exists.")
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": "Glific Auth Log",
        "module": "TAP Buddy",
        "custom": 1,
        "is_submittable": 0,
        "fields": [
            {"fieldname": "event", "label": "Event", "fieldtype": "Select", "options": "Refresh Started\nRefresh Succeeded\nRefresh Failed\nToken Expiry Detected\nHealth Check"},
            {"fieldname": "severity", "label": "Severity", "fieldtype": "Select", "options": "Info\nWarning\nError\nCritical"},
            {"fieldname": "message", "label": "Message", "fieldtype": "Small Text"},
            {"fieldname": "expiry_countdown", "label": "Expiry Countdown (mins)", "fieldtype": "Int"},
            {"fieldname": "timestamp", "label": "Timestamp", "fieldtype": "Datetime"}
        ],
        "permissions": [
            {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1}
        ]
    })
    doc.insert()
    frappe.db.commit()
    print("Created Glific Auth Log DocType.")

if __name__ == "__main__":
    create_doctype()
