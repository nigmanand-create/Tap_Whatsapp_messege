import frappe
from tap_buddy.services.template_renderer import render_template

@frappe.whitelist()
def preview_message(template_name, school_name=None):
    """
    API endpoint to preview a rendered template.
    Sprint 1: Stub implementation. Real version will fetch sample data.
    """
    if not template_name:
        return ""
        
    template = frappe.get_value("WhatsApp Template", template_name, "message")
    if not template:
        # Backward-compatible fallback if old field name exists in data
        template = frappe.get_value("WhatsApp Template", template_name, "message_body")
    if not template:
        return ""
        
    context = {
        "school_name": school_name or "Sample School Name",
        "principal_name": "Sample Principal",
        "district": "Sample District"
    }
    
    return render_template(template, context)

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_populated_collections(doctype, txt, searchfield, start, page_len, filters):
    conditions = []
    if txt:
        conditions.append("(c.collection_name LIKE %(txt)s OR c.name LIKE %(txt)s)")
        
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    
    sql = f"""
        SELECT c.name, c.collection_name
        FROM `tabWhatsApp Group Collection` c
        INNER JOIN `tabWhatsApp Group Collection Mapping` m ON m.collection = c.name
        {where_clause}
        GROUP BY c.name
        ORDER BY c.collection_name ASC
        LIMIT %(page_len)s OFFSET %(start)s
    """
    
    return frappe.db.sql(sql, {
        "txt": f"%{txt}%",
        "start": start,
        "page_len": page_len
    })
