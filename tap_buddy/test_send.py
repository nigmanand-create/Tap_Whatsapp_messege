import frappe
from tap_buddy.services.glific_client import GlificClient

def execute():
    try:
        print("Initializing Glific...")
        client = GlificClient()
        resp = client.send_message("8595701049", "Hello! This is a test message from TAP Buddy integration.")
        print("Sent successfully:", resp)
    except Exception as e:
        print("Failed to send:", e)

