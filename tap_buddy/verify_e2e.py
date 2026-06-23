import frappe
from frappe.utils import now_datetime
import time
import json
from tap_buddy.tasks.scheduler import dispatch_campaign

def run():
    frappe.db.rollback()
    frappe.cache().set_value("mock_glific", 0) # Real execution
    
    # 1. Database Mapping Check
    print("\n=== Phase 3: Verify Database Mapping ===")
    wag = frappe.get_doc("WhatsApp Group", "WAG-12125")
    print(f"WhatsApp Group: {wag.name}")
    print(f"glific_group_id: {wag.glific_group_id}")
    mappings = frappe.get_all("WhatsApp Group Collection Mapping", filters={"whatsapp_group": wag.name}, fields=["collection", "collection.glific_collection_id"])
    print(f"Collection Mapping: {mappings[0].get('collection')}")
    print(f"Collection: {mappings[0].get('collection')}")
    print(f"glific_collection_id: {mappings[0].get('glific_collection_id')}")
    
    # 2. Create Fresh Test Campaign
    print("\n=== Phase 4: Create Fresh Test Campaign ===")
    camp = frappe.new_doc("TAP Campaign")
    camp.campaign_name = "E2E Validation " + str(time.time())
    camp.campaign_type = "Flow"
    camp.campaign_channel = "Group"
    camp.glific_flow = "40067"
    camp.send_date = now_datetime().date()
    
    camp.targeting_type = "WhatsApp Group"
    camp.target_group = "WAG-12125"
    
    camp.insert(ignore_permissions=True)
    camp.submit()
    frappe.db.commit()
    
    print(f"Created & Submitted Campaign: {camp.name}")
    
    # Force trigger dispatch to bypass scheduled jobs timing
    print("\n=== Triggering Dispatch... ===")
    try:
        dispatch_campaign(camp.name)
    except Exception as e:
        print(f"Dispatch Error: {e}")
        
    frappe.db.commit()
    
    # 3. Verify Delivery
    print("\n=== Phase 7: Verify Delivery ===")
    recs = frappe.get_all("Campaign Recipient", filters={"campaign": camp.name}, fields=["name", "status", "failure_reason"])
    for r in recs:
        print(f"Recipient: {r.name} | Status: {r.status} | Error: {r.failure_reason}")
        
        attempts = frappe.get_all("Dispatch Attempt", filters={"recipient": r.name}, fields=["name", "status", "provider_message_id", "error_message"])
        for a in attempts:
            print(f"  Attempt: {a.name} | Status: {a.status} | Provider ID: {a.provider_message_id} | Error: {a.error_message}")
            
    # Load campaign counts
    camp.reload()
    print(f"Campaign Total: {camp.total_recipients} | Sent: {camp.sent_count} | Failed: {camp.failed_count}")
    
    # Print a marker so we know where to grep logs
    print(f"MARKER_CAMPAIGN={camp.name}")
