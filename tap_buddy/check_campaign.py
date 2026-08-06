import frappe

def run():
    camp = frappe.get_doc("TAP Campaign", "TAP-2026-00346-8")
    print(f"Status: {camp.status}")
    print(f"Glific Flow: {camp.glific_flow}")
    print(f"Targeting: {camp.targeting_type}")
    recipients = frappe.get_all("TAP Campaign Recipient", filters={"parent": "TAP-2026-00346-8"}, fields=["name", "recipient", "status", "failure_reason", "glific_contact_id"])
    for r in recipients:
        print(f"Recipient: {r}")
