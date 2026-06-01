import frappe
from frappe.utils import now_datetime, add_to_date

def run():
    print("--- CREATING CAMPAIGN 3 MIN IN FUTURE ---")
    
    current_time = now_datetime()
    future_time = add_to_date(current_time, minutes=3)
    
    doc = frappe.new_doc("TAP Campaign")
    doc.campaign_name = "tap_campain_011"
    doc.template = "tap_greeting_test_001"
    doc.message_template = "Hello {{1}}, this is an auto-triggered scheduled message from TAP Buddy."
    doc.targeting_type = "School Group"
    doc.school_group = "testing full scale"
    doc.send_date = future_time
    
    doc.insert(ignore_permissions=True)
    doc.submit()
    
    campaign_name = doc.name
    
    print(f"✅ Campaign Created!")
    print(f"Campaign ID: {campaign_name}")
    print(f"Current Time: {current_time.strftime('%H:%M:%S')}")
    print(f"Scheduled Send Time: {future_time.strftime('%H:%M:%S')}")
    print(f"Current Status: {frappe.db.get_value('TAP Campaign', campaign_name, 'status')}")
