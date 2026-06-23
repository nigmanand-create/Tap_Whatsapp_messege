import frappe
import json

def run():
    frappe.db.rollback()
    
    camp_id = "TAP-2026-00310"
    print(f"--- Forensic Dump for {camp_id} ---")
    camp = frappe.get_doc("TAP Campaign", camp_id)
    print(f"Status: {camp.status}")
    print(f"Flow ID Used: {camp.glific_flow}")
    
    print("\n--- Campaign Recipients ---")
    recs = frappe.get_all("Campaign Recipient", filters={"campaign": camp_id}, fields=["*"])
    for r in recs:
        print(r)
        
    print("\n--- Dispatch Attempts ---")
    groups = set()
    for r in recs:
        if r.whatsapp_group:
            groups.add(r.whatsapp_group)
            
        attempts = frappe.get_all("Dispatch Attempt", filters={"recipient": r.name}, fields=["*"])
        for a in attempts:
            print(json.dumps(a, default=str, indent=2))
            
    print("\n--- Group & Mapping Info ---")
    for group_name in groups:
        wag = frappe.get_doc("WhatsApp Group", group_name)
        print(f"Group: {wag.name}")
        print(f"Local ID (name): {wag.name}")
        print(f"glific_group_id: {wag.glific_group_id}")
        
        mappings = frappe.get_all("WhatsApp Group Collection Mapping", filters={"whatsapp_group": wag.name}, fields=["collection", "collection.glific_collection_id"])
        print(f"Mapped Collection ID: {mappings}")
