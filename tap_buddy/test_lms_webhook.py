import frappe
from tap_buddy.api.lms_webhook import handle
from tap_buddy.services.lms_ingestion import enqueue_lms_events

def execute():
    try:
        body = '{"event_type": "assignment.due", "student_id": "student_abc", "due_date": "2026-05-28"}'
        payload = frappe.parse_json(body)
        event_names = enqueue_lms_events(payload, body, "test_sig")
        print("SUCCESS:", event_names)
    except Exception as e:
        print("EXCEPTION:")
        import traceback
        traceback.print_exc()
