import frappe

def run():
    # 1. TAP Buddy Settings
    if not frappe.db.exists("DocType", "TAP Buddy Settings"):
        doc = frappe.new_doc("DocType")
        doc.name = "TAP Buddy Settings"
        doc.module = "TAP Buddy"
        doc.custom = 0
        doc.issingle = 1
        fields = [
            {"fieldname": "api_settings_sec", "fieldtype": "Section Break", "label": "Glific API Settings"},
            {"fieldname": "glific_url", "fieldtype": "Data", "label": "Glific URL", "reqd": 1, "description": "Base URL of the Glific API (e.g. https://api.glific.com/v1)"},
            {"fieldname": "glific_token", "fieldtype": "Password", "label": "Glific Token", "reqd": 1, "description": "API Token for authentication"},
            {"fieldname": "col_break_1", "fieldtype": "Column Break"},
            {"fieldname": "sync_mode_fallback", "fieldtype": "Check", "label": "Enable Synchronous Fallback", "default": "0", "description": "Bypass background queue and dispatch immediately. Only for debugging!"},
            
            {"fieldname": "dispatch_sec", "fieldtype": "Section Break", "label": "Dispatch Settings"},
            {"fieldname": "batch_size", "fieldtype": "Int", "label": "Batch Size", "default": "50", "reqd": 1},
            {"fieldname": "rate_limit", "fieldtype": "Int", "label": "Rate Limit (messages/min)", "default": "20", "reqd": 1},
            {"fieldname": "col_break_2", "fieldtype": "Column Break"},
            {"fieldname": "retry_count", "fieldtype": "Int", "label": "Max Retry Count", "default": "3", "reqd": 1},
            {"fieldname": "dispatch_start_hour", "fieldtype": "Time", "label": "Dispatch Start Time", "default": "09:00:00", "reqd": 1},
            {"fieldname": "dispatch_end_hour", "fieldtype": "Time", "label": "Dispatch End Time", "default": "18:00:00", "reqd": 1},
        ]
        for f in fields:
            doc.append("fields", f)
        doc.insert()
        print("Created TAP Buddy Settings")

    # 2. School Group Member
    if not frappe.db.exists("DocType", "School Group Member"):
        doc = frappe.new_doc("DocType")
        doc.name = "School Group Member"
        doc.module = "TAP Buddy"
        doc.custom = 0
        doc.istable = 1
        doc.editable_grid = 1
        fields = [
            {"fieldname": "school", "fieldtype": "Link", "options": "School", "label": "School", "reqd": 1, "in_list_view": 1},
            {"fieldname": "udise_code", "fieldtype": "Data", "label": "UDISE Code", "read_only": 1, "fetch_from": "school.udise_code", "in_list_view": 1},
            {"fieldname": "block", "fieldtype": "Data", "label": "Block", "read_only": 1, "fetch_from": "school.block", "in_list_view": 1},
        ]
        for f in fields:
            doc.append("fields", f)
        doc.insert()
        print("Created School Group Member")

    # 3. School Group
    if not frappe.db.exists("DocType", "School Group"):
        doc = frappe.new_doc("DocType")
        doc.name = "School Group"
        doc.module = "TAP Buddy"
        doc.custom = 0
        doc.autoname = "field:group_name"
        fields = [
            {"fieldname": "group_name", "fieldtype": "Data", "label": "Group Name", "reqd": 1, "unique": 1},
            {"fieldname": "is_active", "fieldtype": "Check", "label": "Is Active", "default": "1"},
            {"fieldname": "description", "fieldtype": "Small Text", "label": "Description"},
            {"fieldname": "members_sec", "fieldtype": "Section Break"},
            {"fieldname": "members", "fieldtype": "Table", "options": "School Group Member", "label": "Schools"},
        ]
        for f in fields:
            doc.append("fields", f)
        doc.insert()
        print("Created School Group")

    frappe.db.commit()
