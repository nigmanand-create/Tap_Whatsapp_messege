import frappe
frappe.init(site="tapbuddy.local")
frappe.connect()
from tap_buddy.services.glific_template_service import send_test_message
try:
    res = send_test_message(phone="+918595701049", template_shortcode="pta_meeting_alert_v2")
    print("SUCCESS:", res)
except Exception as e:
    import traceback
    traceback.print_exc()
