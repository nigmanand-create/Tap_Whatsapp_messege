import frappe
from frappe.utils import now_datetime, add_to_date

def run():
    print("--- CREATING CAMPAIGN 5 MIN IN FUTURE ---")
    
    # 1. Create a test campaign scheduled 5 minutes in the future
    current_time = now_datetime()
    future_time = add_to_date(current_time, minutes=5)
    
    doc = frappe.new_doc("TAP Campaign")
    doc.campaign_name = "tap_campain_010"
    doc.template = "tap_greeting_test_001"
    doc.message_template = "Hello {{1}}, this is a test message from TAP Buddy. Have a great day!"
    doc.targeting_type = "School Group"
    doc.school_group = "testing full scale"
    doc.send_date = future_time
    
    doc.insert(ignore_permissions=True)
    doc.submit()
    
    campaign_name = doc.name
    
    print(f"✅ Successfully created and submitted Campaign!")
    print(f"Campaign ID: {campaign_name}")
    print(f"Campaign Name: {doc.campaign_name}")
    print(f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Scheduled Send Time: {future_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Current Status: {frappe.db.get_value('TAP Campaign', campaign_name, 'status')}")
    print("-----------------------------------------")
    print("Ab Frappe Desk me UI open karke dekh sakte ho, ye campaign 'Queued' status me aa gaya hoga.")
