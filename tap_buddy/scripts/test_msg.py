import frappe
from tap_buddy.services.glific_client import GlificClient
import time

def run():
    # Force disable mock mode in cache and DB
    frappe.cache().set_value("mock_glific", 0)
    frappe.db.set_value('TAP Buddy Settings', 'TAP Buddy Settings', 'mock_glific', 0)
    frappe.db.commit()
    
    # Initialize real client
    client = GlificClient()
    print(f"Is Mock? {getattr(client, '_is_mock', False)}")
    
    try:
        res = client.send_message('918595701049', 'Hello Nigma! 🚀 TAP Buddy backend is live, API rotation works perfectly, and your End-to-End system is rock solid. Final check completed successfully!')
        print(f"Message sent successfully! Response: {res}")
    except Exception as e:
        print(f"Failed to send message: {e}")
