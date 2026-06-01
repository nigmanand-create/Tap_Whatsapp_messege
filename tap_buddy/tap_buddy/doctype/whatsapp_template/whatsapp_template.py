import re
import frappe
from frappe.model.document import Document


class WhatsAppTemplate(Document):
    def validate(self):
        """Auto-detect Mustache-like params in `message` and store them in `detected_params`."""
        msg = (self.message or "")
        params = re.findall(r'{{\s*([^}]+?)\s*}}', msg)
        if params:
            # store as comma-separated list
            self.detected_params = ",".join([p.strip() for p in params])
        else:
            self.detected_params = ""

@frappe.whitelist()
def sync_glific_templates():
    from tap_buddy.services.glific_client import GlificClient
    client = GlificClient()
    
    query = """
    query sessionTemplates($filter: SessionTemplateFilter, $opts: Opts) {
        sessionTemplates(filter: $filter, opts: $opts) {
            id
            label
            body
            shortcode
            status
            category
            numberParameters
            isHsm
        }
    }
    """
    
    templates = []
    offset = 0
    limit = 500
    while True:
        try:
            data = client._graphql_request(query, {"opts": {"limit": limit, "offset": offset, "order": "DESC"}})
            batch = data.get("sessionTemplates") or []
            templates.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        except Exception as e:
            frappe.throw(f"Failed to fetch templates from Glific: {str(e)}")
        
    count = 0
    for t in templates:
        if t.get("status") != "APPROVED":
            continue
            
        shortcode = t.get("shortcode")
        if not shortcode:
            continue
            
        exists = frappe.db.exists("WhatsApp Template", {"glific_shortcode": shortcode})
        if exists:
            doc = frappe.get_doc("WhatsApp Template", exists)
            doc.message = t.get("body") or "No message body provided"
            doc.glific_template_id = shortcode
            doc.glific_db_id = t.get("id")
            doc.glific_push_status = "Approved"
            doc.save(ignore_permissions=True)
            count += 1
        else:
            doc = frappe.get_doc({
                "doctype": "WhatsApp Template",
                "template_name": shortcode,
                "message": t.get("body") or "No message body provided",
                "glific_shortcode": shortcode,
                "language": "English",
                "category": t.get("category") or "UTILITY",
                "glific_template_id": shortcode,
                "glific_db_id": t.get("id"),
                "glific_push_status": "Approved"
            })
            doc.insert(ignore_permissions=True)
            count += 1
            
    frappe.db.commit()
    return {"status": "success", "message": f"Successfully synced {count} approved templates from Glific."}