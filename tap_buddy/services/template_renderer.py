import frappe
from bs4 import BeautifulSoup

def render_template(template_content, context=None):
    """
    Renders a message template with the given context.
    Also strips HTML tags since templates might be authored in a Rich Text editor,
    but WhatsApp expects plain text.
    """
    if not template_content:
        return ""
    
    # 1. Strip HTML tags using BeautifulSoup (cleaner than regex)
    soup = BeautifulSoup(template_content, "html.parser")
    # Get text, using newlines for block elements
    plain_text = soup.get_text(separator="\n").strip()
    
    # 2. Render variables using Frappe's jinja environment
    try:
        render_context = context or {}
        rendered = frappe.render_template(plain_text, render_context)
        return rendered
    except Exception as e:
        frappe.log_error(title="Template Rendering Error", message=str(e))
        # Return plain text as fallback if rendering fails
        return plain_text
