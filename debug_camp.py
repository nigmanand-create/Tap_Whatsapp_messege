import frappe

frappe.init(site="tapbuddy.local")
frappe.connect()

camp = frappe.get_doc("TAP Campaign", "TAP-2026-00299")
print("--- Campaign Data ---")
print(f"Name: {camp.name}")
print(f"Status: {camp.status}")
print(f"Type: {camp.campaign_type}")
print(f"Targeting: {camp.targeting_type}")
print(f"Target Group: {camp.target_group}")
print(f"Target Collection: {camp.target_collection}")
print(f"Total Recipients: {camp.total_recipients}")
print(f"Sent Count: {camp.sent_count}")
print(f"Failed Count: {camp.failed_count}")

print("\n--- Recipients ---")
recipients = frappe.get_all("Campaign Recipient", filters={"parent": camp.name}, fields=["name", "status"])
print(f"Found {len(recipients)} Campaign Recipients.")

if camp.target_group:
    members = frappe.get_all("LMS Student", filters={"group_labels": ["like", f"%{camp.target_group}%"]}, fields=["name"])
    print(f"LMS Students matching group label: {len(members)}")
    
    # Check what table actually links to WhatsApp Group. Maybe it's "School Group Member"?
    
