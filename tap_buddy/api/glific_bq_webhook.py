import json
import frappe

from tap_buddy.services.bigquery_executor import execute_tvf, JSONEncoderCustom

ALLOWED_RESOURCES = {
    "student_context": "get_student_context_v1",
    "attendance_context": "get_attendance_context_v1",
    "assignment_context": "get_assignment_context_v1"
}

@frappe.whitelist(allow_guest=True)
def handle():
    """
    Generic webhook endpoint for Glific Flows to dynamically fetch BigQuery context data.
    """
    frappe.local.response.content_type = "application/json"
    
    settings = frappe.get_single("TAP Buddy Settings")
    secret = settings.get_password("webhook_secret") if hasattr(settings, "get_password") else settings.webhook_secret
    
    if not secret:
        frappe.local.response.http_status_code = 500
        return {"error": "Webhook secret is not configured in TAP Buddy Settings."}

    raw_body = frappe.request.get_data(as_text=True)
    if not raw_body:
        frappe.local.response.http_status_code = 400
        return {"error": "Missing JSON payload."}

    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError:
        frappe.local.response.http_status_code = 400
        return {"error": "Invalid JSON payload."}

    provided_secret = payload.get("secret")
    if not provided_secret or provided_secret != secret:
        frappe.local.response.http_status_code = 401
        return {"error": "Unauthorized."}

    resource_key = payload.get("resource")
    if not resource_key:
        frappe.local.response.http_status_code = 400
        return {"error": "Missing 'resource' parameter."}

    if resource_key not in ALLOWED_RESOURCES:
        frappe.local.response.http_status_code = 403
        return {"error": f"Resource '{resource_key}' is not whitelisted."}

    tvf_name = ALLOWED_RESOURCES[resource_key]

    contact = payload.get("contact", {})
    phone = contact.get("phone")
    if not phone:
        frappe.local.response.http_status_code = 400
        return {"error": "Missing 'contact.phone' in payload."}

    # Extract other payload variables to support future flexibility
    parameters = payload.get("parameters", {})
    parameters["phone"] = phone

    mock_mode = frappe.utils.cint(payload.get("mock_mode", 0))

    try:
        frappe.logger("bigquery").info(f"[Glific BQ Webhook] Executing {tvf_name} for phone {phone} (mock={mock_mode})")
        
        # Execute the TVF
        rows = execute_tvf(tvf_name, parameters, mock_mode=bool(mock_mode))

        # We must return a flat JSON structure for Glific variables
        if not rows:
            return {}

        safe_row_json = json.dumps(rows[0], cls=JSONEncoderCustom)
        safe_row = json.loads(safe_row_json)

        if frappe.flags.in_test:
            return safe_row

        # Update frappe.response directly instead of returning to avoid {"message": {...}} wrapper
        frappe.response.update(safe_row)
        return

    except Exception as e:
        frappe.logger("bigquery").error(f"[Glific BQ Webhook] Exception: {str(e)}")
        exc_name = type(e).__name__
        if exc_name == "NotFound":
            frappe.local.response.http_status_code = 404
            return {"error": "Resource does not exist in API dataset."}
        elif exc_name == "BadRequest":
            frappe.local.response.http_status_code = 400
            return {"error": "Invalid parameters passed to BigQuery routine.", "details": str(e)}
        else:
            frappe.local.response.http_status_code = 500
            return {"error": "Internal Server Error", "details": str(e)}
