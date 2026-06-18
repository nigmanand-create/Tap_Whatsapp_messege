import frappe

def run():
    doc = frappe.get_doc("DocType", "TAP Campaign")
    
    # Check if fields exist
    has_type = any(f.fieldname == "campaign_type" for f in doc.fields)
    has_flow = any(f.fieldname == "glific_flow" for f in doc.fields)
    
    if not has_type:
        # Find index of 'template' to insert before
        idx = next((i for i, f in enumerate(doc.fields) if f.fieldname == "template"), 0)
        
        type_field = {
            "fieldname": "campaign_type",
            "label": "Campaign Type",
            "fieldtype": "Select",
            "options": "Template\nFlow",
            "default": "Template",
            "reqd": 1,
            "in_list_view": 1
        }
        
        flow_field = {
            "fieldname": "glific_flow",
            "label": "Glific Flow",
            "fieldtype": "Link",
            "options": "Glific Flow",
            "depends_on": "eval:doc.campaign_type=='Flow'",
            "mandatory_depends_on": "eval:doc.campaign_type=='Flow'"
        }
        
        doc.append("fields", flow_field)
        doc.append("fields", type_field)
        
        # Sort manually: place them before `template`
        doc.fields.sort(key=lambda x: x.idx) # restore original order
        # We need to insert them properly. A safer way is to rebuild the list
        new_fields = []
        for f in doc.fields:
            if f.fieldname in ("campaign_type", "glific_flow"):
                continue
            if f.fieldname == "template":
                new_fields.append(frappe._dict(type_field))
                new_fields.append(frappe._dict(flow_field))
            new_fields.append(f)
            
        doc.fields = new_fields
        for i, f in enumerate(doc.fields):
            f.idx = i + 1
            
        # Update depends_on for template
        for f in doc.fields:
            if f.fieldname == "template":
                f.depends_on = "eval:doc.campaign_type=='Template'"
                f.mandatory_depends_on = "eval:doc.campaign_type=='Template'"
            if f.fieldname == "variable_mappings":
                f.depends_on = "eval:doc.campaign_type=='Template' || doc.campaign_type=='Flow'"
                
        doc.save(ignore_permissions=True)
        frappe.db.commit()
        print("TAP Campaign updated successfully")
    else:
        print("TAP Campaign already updated")

