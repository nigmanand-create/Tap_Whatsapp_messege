import frappe
from tap_buddy.services.glific_client import GlificClient
import traceback

def sync_collections_and_groups():
    """
    Fetches Group Collections and WhatsApp Groups from Glific,
    then idempotently upserts them and their Many-to-Many mappings into TAP Buddy.
    """
    frappe.logger("tap_buddy_sync").info("Starting WhatsApp Group Collection Sync")
    try:
        client = GlificClient()
        
        # 1. Fetch from Glific
        collections_data = client.get_group_collections()
        wa_groups_data = client.get_whatsapp_groups()
        
        # 2. Upsert Collections
        for col in collections_data:
            col_id = str(col.get("id"))
            col_name = col.get("label", "")
            group_count = col.get("waGroupsCount", 0)
            
            # Upsert WhatsApp Group Collection
            if not frappe.db.exists("WhatsApp Group Collection", {"glific_collection_id": col_id}):
                doc = frappe.new_doc("WhatsApp Group Collection")
                doc.glific_collection_id = col_id
                doc.collection_name = col_name
                doc.group_count = group_count
                doc.last_synced_at = frappe.utils.now_datetime()
                doc.insert(ignore_permissions=True)
            else:
                doc_name = frappe.db.get_value("WhatsApp Group Collection", {"glific_collection_id": col_id}, "name")
                doc = frappe.get_doc("WhatsApp Group Collection", doc_name)
                doc.collection_name = col_name
                doc.group_count = group_count
                doc.last_synced_at = frappe.utils.now_datetime()
                doc.save(ignore_permissions=True)
                
        # 3. Upsert WhatsApp Groups and Mappings
        for wag in wa_groups_data:
            wag_id = str(wag.get("id"))
            wag_name = wag.get("label", "")
            last_comm_at = wag.get("lastCommunicationAt")
            associated_collections = wag.get("groups") or []
            
            # Upsert WhatsApp Group
            if not frappe.db.exists("WhatsApp Group", {"glific_group_id": wag_id}):
                wag_doc = frappe.new_doc("WhatsApp Group")
                wag_doc.glific_group_id = wag_id
                wag_doc.group_name = wag_name
                wag_doc.status = "Active"
                if last_comm_at:
                    wag_doc.last_communication_at = last_comm_at
                wag_doc.last_synced_at = frappe.utils.now_datetime()
                wag_doc.insert(ignore_permissions=True)
            else:
                wag_name_local = frappe.db.get_value("WhatsApp Group", {"glific_group_id": wag_id}, "name")
                wag_doc = frappe.get_doc("WhatsApp Group", wag_name_local)
                wag_doc.group_name = wag_name
                if last_comm_at:
                    wag_doc.last_communication_at = last_comm_at
                wag_doc.last_synced_at = frappe.utils.now_datetime()
                wag_doc.save(ignore_permissions=True)
            
            # Process Mappings
            # First, delete existing mappings for this WhatsApp Group to cleanly re-insert
            frappe.db.sql("DELETE FROM `tabWhatsApp Group Collection Mapping` WHERE whatsapp_group = %s", (wag_doc.name,))
            
            # Re-insert Mappings
            for assoc_col in associated_collections:
                assoc_col_id = str(assoc_col.get("id"))
                
                # Verify Collection exists locally (it should since we synced collections first)
                col_name_local = frappe.db.get_value("WhatsApp Group Collection", {"glific_collection_id": assoc_col_id}, "name")
                if col_name_local:
                    mapping_doc = frappe.new_doc("WhatsApp Group Collection Mapping")
                    mapping_doc.collection = col_name_local
                    mapping_doc.whatsapp_group = wag_doc.name
                    mapping_doc.insert(ignore_permissions=True)
        
        frappe.db.commit()
        frappe.logger("tap_buddy_sync").info(f"WhatsApp Group Collection Sync completed. Collections: {len(collections_data)}, Groups: {len(wa_groups_data)}")
        return {"status": "success", "collections_synced": len(collections_data), "groups_synced": len(wa_groups_data)}
        
    except Exception as e:
        frappe.db.rollback()
        error_trace = traceback.format_exc()
        frappe.logger("tap_buddy_sync").error(f"WhatsApp Group Collection Sync failed: {str(e)}\n{error_trace}")
        return {"status": "error", "message": str(e)}

@frappe.whitelist()
def trigger_manual_sync():
    """Triggered via the 'Sync With Glific' UI button."""
    frappe.has_permission("WhatsApp Group Collection", throw=True)
    frappe.enqueue("tap_buddy.services.group_collection_sync.sync_collections_and_groups", queue="default", timeout=1000)
    return "Sync initiated in background."
