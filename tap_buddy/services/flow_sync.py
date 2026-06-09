import frappe
from tap_buddy.services.glific_client import GlificClient

def sync_glific_flows():
    """
    Fetch active flows from Glific and upsert them into the local 'Glific Flow' DocType.
    """
    frappe.logger("tap_buddy_sync").info("Starting Glific flows sync...")
    client = GlificClient()
    
    try:
        # Fetch up to 1000 active flows (configurable if needed)
        flows = client.get_flows(is_active=True, limit=1000)
    except Exception as e:
        frappe.logger("tap_buddy_sync").exception("Failed to fetch flows from Glific")
        return False
        
    count_upserted = 0
    for flow in flows:
        flow_id = str(flow.get("id"))
        if not flow_id:
            continue
            
        doc_data = {
            "doctype": "Glific Flow",
            "flow_id": flow_id,
            "flow_name": flow.get("name") or f"Flow {flow_id}",
            "flow_type": flow.get("flowType"),
            "is_active": flow.get("isActive"),
            "is_background": flow.get("isBackground")
        }
        
        if frappe.db.exists("Glific Flow", flow_id):
            doc = frappe.get_doc("Glific Flow", flow_id)
            doc.update(doc_data)
            doc.save(ignore_permissions=True)
        else:
            doc = frappe.get_doc(doc_data)
            doc.insert(ignore_permissions=True)
            
        count_upserted += 1
        
    frappe.db.commit()
    frappe.logger("tap_buddy_sync").info(f"Successfully synced {count_upserted} flows.")
    return True
