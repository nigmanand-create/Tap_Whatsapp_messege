import frappe
from tap_buddy.tasks.scheduler import process_webhook_queue

def execute():
    try:
        process_webhook_queue()
        print("SUCCESS")
    except Exception as e:
        print("EXCEPTION:")
        import traceback
        traceback.print_exc()
