import frappe
from frappe.utils import now_datetime
import time

def run_e2e_test():
    frappe.init(site="tapbuddy.local")
    frappe.connect()

    # Clean up DB for test predictability
    frappe.db.sql("DELETE FROM `tabSchool` WHERE school_name LIKE 'Test School %'")
    frappe.db.sql("DELETE FROM `tabSchool Group` WHERE group_name = 'testing full scale'")
    frappe.db.sql("DELETE FROM `tabSchool Group Member`")
    frappe.db.sql("DELETE FROM `tabTAP Campaign` WHERE campaign_name = 'E2E Test Campaign'")
    frappe.db.sql("DELETE FROM `tabCampaign Recipient`")
    frappe.db.sql("DELETE FROM `tabDispatch Attempt`")
    frappe.db.sql("DELETE FROM `tabMessage Log`")
    frappe.db.commit()

    print("--- 1. Creating School 1 ---")
    s1 = frappe.get_doc({
        "doctype": "School",
        "school_name": "Test School 1",
        "whatsapp_number": "+918595701049",
        "lms_school_status": "Active"
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"School 1 Created: {s1.name} with number {s1.whatsapp_number}")

    print("--- 2. Creating School 2 ---")
    s2 = frappe.get_doc({
        "doctype": "School",
        "school_name": "Test School 2",
        "whatsapp_number": "+918076398155",
        "lms_school_status": "Active"
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"School 2 Created: {s2.name} with number {s2.whatsapp_number}")

    print("--- 3. Creating School Group ---")
    group = frappe.get_doc({
        "doctype": "School Group",
        "group_name": "testing full scale",
        "is_active": 1,
        "members": [
            {"school": s1.name},
            {"school": s2.name}
        ]
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    print(f"School Group Created: {group.name} with {len(group.members)} members")

    print("--- 4. Creating TAP Campaign ---")
    campaign = frappe.get_doc({
        "doctype": "TAP Campaign",
        "campaign_name": "E2E Test Campaign",
        "targeting_type": "School Group",
        "school_group": group.name,
        "template": "tap_greeting_test_001",
        "send_date": now_datetime(),
        "status": "Draft"
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    print("--- 5. Submitting Campaign ---")
    campaign.docstatus = 1
    campaign.save(ignore_permissions=True)
    frappe.db.commit()
    print(f"Campaign Submitted. Status: {campaign.status}")

    # Explicitly dispatch to bypass the queue worker for the test script
    from tap_buddy.tasks.scheduler import dispatch_campaign, sync_campaign_counts
    print("--- Dispatching Campaign ---")
    dispatch_campaign(campaign.name)
    frappe.db.commit()
    
    # Wait for execution and sync counts
    time.sleep(2)
    sync_campaign_counts()
    frappe.db.commit()
    
    campaign.reload()
    print(f"\nFinal Campaign Status: {campaign.status}")
    print(f"Total Recipients: {campaign.total_recipients}")
    print(f"Sent Count: {campaign.sent_count}")
    print(f"Failed Count: {campaign.failed_count}")

    print("\n--- Recipient Records ---")
    recipients = frappe.get_all("Campaign Recipient", filters={"campaign": campaign.name}, fields=["name", "school", "status"])
    for r in recipients:
        print(f"Recipient: {r.name}, School: {r.school}, Final Status: {r.status}")
        
    print("\n--- Dispatch Attempts ---")
    attempts = frappe.get_all("Dispatch Attempt", filters={"campaign": campaign.name}, fields=["name", "recipient", "status", "error_message"])
    for a in attempts:
        print(a)
        
    print("\n--- Message Logs ---")
    logs = frappe.get_all("Message Log", filters={"campaign": campaign.name}, fields=["name", "school", "phone_number", "status", "provider_message_id", "api_response"])
    for l in logs:
        sent_str = "YES" if l.status == "Sent" else "NO"
        msg_id = l.provider_message_id or "N/A"
        print(f"\nMessage Log: {l.name}")
        print(f"School: {l.school}")
        print(f"Phone: {l.phone_number}")
        print(f"Sent = {sent_str}")
        print(f"Message ID: {msg_id}")
        print(f"Final Status: {l.status}")
        print(f"Glific Response: {l.api_response}")

if __name__ == "__main__":
    run_e2e_test()
