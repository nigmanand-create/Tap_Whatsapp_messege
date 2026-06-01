import frappe

def update_tap_campaign():
    doctype_name = "TAP Campaign"
    
    doc = frappe.get_doc("DocType", doctype_name)
    
    # Check if field already exists
    if any(f.fieldname == "variable_mappings" for f in doc.fields):
        print("Field 'variable_mappings' already exists in TAP Campaign.")
        return

    # Add the Table field
    doc.append("fields", {
        "fieldname": "variable_mappings",
        "label": "Variable Mappings",
        "fieldtype": "Table",
        "options": "Template Variable Mapping",
        "description": "Map the variables required by the selected WhatsApp template."
    })
    
    doc.save(ignore_permissions=True)
    print(f"Successfully added 'variable_mappings' field to {doctype_name}")

if __name__ == "__main__":
    update_tap_campaign()
