import frappe

def execute(dry_run=True, rollback=False):
    print("--- WhatsApp Group ID Migration ---")
    print(f"Mode: {'ROLLBACK' if rollback else 'DRY RUN' if dry_run else 'REPAIR'}")
    
    wags = frappe.get_all("WhatsApp Group", fields=["name", "glific_group_id", "group_name"])
    
    fixed_count = 0
    for wag in wags:
        mappings = frappe.get_all(
            "WhatsApp Group Collection Mapping",
            filters={"whatsapp_group": wag.name},
            fields=["collection", "collection.glific_collection_id"]
        )
        
        if mappings:
            col_id = mappings[0].get("glific_collection_id")
            # If the glific_group_id is set to the collection id (the stale override)
            if str(wag.glific_group_id) == str(col_id):
                # We need to restore it to the actual waGroup ID.
                # However, during normal sync, the glific_group_id is the waGroup ID. 
                # If we don't know the original ID, we might have to re-sync.
                # But typically, wag.name is something like WAG-12125, where 12125 is the actual ID.
                expected_id = wag.name.replace("WAG-", "")
                
                print(f"Found overridden record: {wag.name} -> {wag.glific_group_id}")
                print(f"Action: Revert glific_group_id to {expected_id}")
                
                if not dry_run:
                    frappe.db.set_value("WhatsApp Group", wag.name, "glific_group_id", expected_id)
                fixed_count += 1
                
        # Handle the manual override I did: WAG-3725 was set to 3725, but what if WAG-12125 was set to 20996?
        if str(wag.glific_group_id) == "20996" and wag.name == "WAG-12125":
            expected_id = "12125"
            print(f"Found specific override: {wag.name} -> {wag.glific_group_id}")
            print(f"Action: Revert glific_group_id to {expected_id}")
            if not dry_run:
                frappe.db.set_value("WhatsApp Group", wag.name, "glific_group_id", expected_id)
            fixed_count += 1

    if not dry_run:
        frappe.db.commit()
        print(f"Successfully repaired {fixed_count} records.")
    else:
        print(f"Dry run complete. Found {fixed_count} records to repair.")

