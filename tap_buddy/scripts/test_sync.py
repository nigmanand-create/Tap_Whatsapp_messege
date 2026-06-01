import frappe
from tap_buddy.tap_buddy.doctype.whatsapp_template.whatsapp_template import sync_glific_templates

def test():
    frappe.init(site="tapbuddy.local")
    frappe.connect()
    
    # 1. verify if mock is deleted
    frappe.db.delete("WhatsApp Template", "mock")
    frappe.db.commit()
    
    # 2. sync templates
    res = sync_glific_templates()
    print("Sync Res:", res)
    
    # 3. get all
    docs = frappe.get_all("WhatsApp Template", fields=["name", "template_name", "message", "glific_push_status"])
    print("DB Templates:", docs)

if __name__ == "__main__":
    test()
