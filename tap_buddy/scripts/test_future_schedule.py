import frappe
from frappe.utils import now_datetime, add_to_date
from tap_buddy.tasks.scheduler import dispatch_campaign

def run():
    print("--- STARTING FUTURE SCHEDULE TEST ---")
    
    # 1. Create a test campaign scheduled 1 hour in the future
    future_time = add_to_date(now_datetime(), hours=1)
    
    doc = frappe.new_doc("TAP Campaign")
    doc.campaign_name = "test_future_dispatch"
    doc.template = "tap_greeting_test_001"
    doc.message_template = "Hello {{1}}, this is a future test message."
    doc.targeting_type = "School Group"
    doc.school_group = "testing full scale"
    doc.send_date = future_time
    
    doc.insert(ignore_permissions=True)
    doc.submit()
    
    campaign_name = doc.name
    print(f"1. Created Campaign: {campaign_name} with send_date: {future_time}")
    print(f"2. Initial Status: {frappe.db.get_value('TAP Campaign', campaign_name, 'status')}")
    
    # 2. Trigger the dispatch job (simulating what on_submit does)
    print("3. Triggering dispatch_campaign() background job manually...")
    dispatch_campaign(campaign_name)
    
    # 3. Check the results
    frappe.db.commit()
    final_status = frappe.db.get_value("TAP Campaign", campaign_name, "status")
    recipients_count = frappe.db.count("Campaign Recipient", {"campaign": campaign_name})
    
    print("--- TEST RESULTS ---")
    print(f"Final Status: {final_status}")
    print(f"Recipients Created: {recipients_count}")
    
    if final_status == "Queued" and recipients_count == 0:
        print("✅ PROOF: The dispatch function exited early and did nothing because the time is in the future!")
        print("This campaign is now stuck as 'Queued' and will never be sent unless a cron job wakes it up.")
    else:
        print("❌ Unexpected behavior.")
