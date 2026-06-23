import frappe
from tap_buddy.services.glific_client import GlificClient
from tap_buddy.tasks.scheduler import _dispatch_flow_campaign

def run():
    print("=== Creating Real E2E Campaign ===")
    
    # Get a random school
    school = frappe.get_all("School", limit=1)
    school_name = school[0].name if school else "Test School"
    if not school:
        frappe.get_doc({"doctype": "School", "school_name": "Test School"}).insert(ignore_permissions=True)
    
    # Create Campaign
    camp = frappe.get_doc({
        "doctype": "TAP Campaign",
        "campaign_name": "E2E Group Flow Validation",
        "campaign_type": "Flow",
        "glific_flow": "40067",
        "school_name": school_name,
        "send_date": frappe.utils.nowdate(),
        "target_whatsapp_groups": [
            {"whatsapp_group": "WAG-12125"}
        ],
        "status": "Draft"
    }).insert(ignore_permissions=True)
    
    camp.status = "Running"
    camp.save(ignore_permissions=True)
    
    # Create Recipient
    rec = frappe.get_doc({
        "doctype": "Campaign Recipient",
        "campaign": camp.name,
        "school": school_name,
        "whatsapp_group": "WAG-12125",
        "status": "Pending"
    }).insert(ignore_permissions=True)
    
    frappe.db.commit()
    
    print(f"Created Campaign: {camp.name}")
    print(f"Created Recipient: {rec.name}")
    
    frappe.cache().set_value("mock_glific", 1)
    client = GlificClient()
    
    print(f"Dispatching to {rec.whatsapp_group}...")
    _dispatch_flow_campaign(client, camp, rec)
    
    # Verify State
    rec.reload()
    print(f"\nResult:")
    print(f"Recipient Status: {rec.status}")
    print(f"Failure Reason: {rec.failure_reason}")
    
    attempts = frappe.get_all("Dispatch Attempt", filters={"recipient": rec.name}, fields=["status", "error_message"])
    for a in attempts:
        print(f"Attempt: {a.status} | Error: {a.error_message}")

