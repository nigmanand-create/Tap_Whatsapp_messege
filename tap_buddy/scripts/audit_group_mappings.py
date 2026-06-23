import frappe

def execute():
    print("--- WhatsApp Group to Glific Collection Mapping Audit ---")
    print(f"{'WhatsApp Group':<20} | {'WhatsApp Group ID':<20} | {'Collection ID':<20} | {'Collection Label':<25} | {'Mapping Status':<15}")
    print("-" * 110)
    
    wags = frappe.get_all("WhatsApp Group", fields=["name", "glific_group_id", "group_name"])
    
    for wag in wags:
        mappings = frappe.get_all(
            "WhatsApp Group Collection Mapping",
            filters={"whatsapp_group": wag.name},
            fields=["collection", "collection.glific_collection_id", "collection.collection_name"]
        )
        
        if not mappings:
            print(f"{wag.name:<20} | {str(wag.glific_group_id):<20} | {'N/A':<20} | {'N/A':<25} | {'UNMAPPED':<15}")
        else:
            for m in mappings:
                col_id = m.get("glific_collection_id") or "N/A"
                col_label = m.get("collection_name") or "N/A"
                
                # Check if someone manually overrode the wag ID to be the col ID
                if str(wag.glific_group_id) == str(col_id):
                    status = "STALE (OVERRIDE)"
                else:
                    status = "VALID"
                
                print(f"{wag.name:<20} | {str(wag.glific_group_id):<20} | {str(col_id):<20} | {str(col_label):<25} | {status:<15}")
                
    print("\nAudit Complete.")
