import frappe
from tap_buddy.services.lms_client import LMSClient

def run():
    print("🔍 Testing LMS API Connection...")
    try:
        settings = frappe.get_single("LMS Integration Settings")
        print(f"Enabled in Settings: {settings.enabled}")
        print(f"Base URL: {settings.lms_base_url}")
        
        client = LMSClient()
        print("✅ LMSClient initialized successfully. Fetching students...")
        
        # Fetch up to 3 students just to see if the connection works
        res = client.get_students(limit_page_length=3)
        
        data = res.get("data", [])
        print(f"✅ Successfully fetched {len(data)} students!")
        for student in data:
            print(student)
            
    except Exception as e:
        print(f"❌ LMS API Check Failed: {e}")
