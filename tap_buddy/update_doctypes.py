import frappe

def run():
    # 1. Update School DocType
    school_doc = frappe.get_doc("DocType", "School")
    existing_fields = [f.fieldname for f in school_doc.fields]
    
    if "udise_code" not in existing_fields:
        school_doc.append("fields", {
            "fieldname": "udise_code",
            "fieldtype": "Data",
            "label": "UDISE Code",
            "unique": 1,
            "insert_after": "school_name"
        })
        
    if "block" not in existing_fields:
        school_doc.append("fields", {
            "fieldname": "block",
            "fieldtype": "Data",
            "label": "Block",
            "insert_after": "udise_code"
        })
        
    school_doc.save()
    print("Updated School DocType")

    # 2. Update TAP Campaign DocType
    campaign_doc = frappe.get_doc("DocType", "TAP Campaign")
    existing_campaign_fields = [f.fieldname for f in campaign_doc.fields]
    
    # Update school_name field to depend on targeting_type
    for f in campaign_doc.fields:
        if f.fieldname == "school_name":
            f.depends_on = 'eval:doc.targeting_type=="Single School"'
            f.mandatory_depends_on = 'eval:doc.targeting_type=="Single School"'
            # remove static reqd if any
            f.reqd = 0
            
    if "targeting_type" not in existing_campaign_fields:
        campaign_doc.append("fields", {
            "fieldname": "targeting_type",
            "fieldtype": "Select",
            "label": "Targeting Type",
            "options": "Single School\nSchool Group",
            "default": "Single School",
            "reqd": 1,
            "insert_after": "campaign_name"
        })
        
    if "school_group" not in existing_campaign_fields:
        campaign_doc.append("fields", {
            "fieldname": "school_group",
            "fieldtype": "Link",
            "options": "School Group",
            "label": "School Group",
            "depends_on": 'eval:doc.targeting_type=="School Group"',
            "mandatory_depends_on": 'eval:doc.targeting_type=="School Group"',
            "insert_after": "targeting_type"
        })
        
    # Counters
    if "total_recipients" not in existing_campaign_fields:
        campaign_doc.append("fields", {"fieldname": "cb_counters", "fieldtype": "Column Break"})
        campaign_doc.append("fields", {"fieldname": "total_recipients", "fieldtype": "Int", "label": "Total Recipients", "read_only": 1})
        campaign_doc.append("fields", {"fieldname": "sent_count", "fieldtype": "Int", "label": "Sent Count", "read_only": 1})
        campaign_doc.append("fields", {"fieldname": "delivered_count", "fieldtype": "Int", "label": "Delivered Count", "read_only": 1})
        campaign_doc.append("fields", {"fieldname": "failed_count", "fieldtype": "Int", "label": "Failed Count", "read_only": 1})
        
    campaign_doc.save()
    print("Updated TAP Campaign DocType")
    
    frappe.db.commit()
