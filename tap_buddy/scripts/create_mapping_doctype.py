import frappe

def create_doctype():
    doctype_name = "Template Variable Mapping"
    
    if frappe.db.exists("DocType", doctype_name):
        print(f"DocType {doctype_name} already exists.")
        return

    doc = frappe.get_doc({
        "doctype": "DocType",
        "name": doctype_name,
        "module": "TAP Buddy",
        "custom": 0,
        "istable": 1,
        "editable_grid": 1,
        "fields": [
            {
                "fieldname": "variable_number",
                "label": "Variable Number",
                "fieldtype": "Int",
                "in_list_view": 1,
                "read_only": 1,
                "columns": 1
            },
            {
                "fieldname": "mapping_type",
                "label": "Mapping Type",
                "fieldtype": "Select",
                "options": "Static Text\nSchool Field\nStudent Field",
                "default": "Static Text",
                "in_list_view": 1,
                "columns": 2
            },
            {
                "fieldname": "static_value",
                "label": "Static Value",
                "fieldtype": "Data",
                "depends_on": "eval:doc.mapping_type == 'Static Text'",
                "in_list_view": 1,
                "columns": 3
            },
            {
                "fieldname": "field_name",
                "label": "Field Name",
                "fieldtype": "Select",
                "options": "\nparent_name\nstudent_name\nphone_number\nschool_name\nudise_code\ncontact_name\nchild_name\nmeeting_date\nmeeting_time",
                "depends_on": "eval:doc.mapping_type != 'Static Text'",
                "in_list_view": 1,
                "columns": 3
            }
        ]
    })
    
    doc.insert(ignore_permissions=True)
    print(f"Successfully created DocType: {doctype_name}")

if __name__ == "__main__":
    create_doctype()
