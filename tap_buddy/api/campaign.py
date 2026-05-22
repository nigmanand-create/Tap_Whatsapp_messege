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
