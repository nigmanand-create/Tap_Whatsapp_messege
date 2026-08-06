import frappe
import json

def add_fields():
    frappe.init(site="tapbuddy.local")
    frappe.connect()

    doctype = frappe.get_doc("DocType", "TAP Campaign")
    
    existing_fieldnames = [f.fieldname for f in doctype.fields]
    
    if "campaign_configuration_section" not in existing_fieldnames:
        doctype.append("fields", {
            "fieldname": "campaign_configuration_section",
            "fieldtype": "Section Break",
            "label": "Campaign Configuration"
        })
        
    if "pi_name" not in existing_fieldnames:
        doctype.append("fields", {
            "fieldname": "pi_name",
            "fieldtype": "Data",
            "label": "PI Name"
        })
        
    if "pi_phone" not in existing_fieldnames:
        doctype.append("fields", {
            "fieldname": "pi_phone",
            "fieldtype": "Data",
            "label": "PI Phone"
        })
        
    if "video_link" not in existing_fieldnames:
        doctype.append("fields", {
            "fieldname": "video_link",
            "fieldtype": "Data",
            "label": "Video Link"
        })
        
    if "teacher_playbook_link" not in existing_fieldnames:
        doctype.append("fields", {
            "fieldname": "teacher_playbook_link",
            "fieldtype": "Data",
            "label": "Teacher Playbook Link"
        })

    doctype.save()
    frappe.db.commit()
    print("Fields added to TAP Campaign")

if __name__ == "__main__":
    add_fields()
