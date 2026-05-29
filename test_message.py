import frappe
from tap_buddy.services.glific_client import GlificClient

frappe.init(site="tapbuddy.local")
frappe.connect()

def test_send():
    print("Initializing GlificClient...")
    client = GlificClient()
    try:
        print("Sending message...")
        resp = client.send_message("8595701049", "Hello from TAP Buddy Live Integration! This is a test message.")
        print("Response:", resp)
    except Exception as e:
        print("Error sending message:", e)

test_send()
