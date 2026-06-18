import json
import hashlib
import frappe
from frappe import _
from tap_buddy.services.bigquery_executor import execute_tvf, JSONEncoderCustom

def get_cache_key(dataset_id, resource, parameters):
    """Generate a deterministic cache key."""
    # sort_keys=True ensures identical parameters yield the same hash
    param_str = json.dumps(parameters, sort_keys=True)
    param_hash = hashlib.sha256(param_str.encode("utf-8")).hexdigest()
    return f"bq_routine:{dataset_id}:{resource}:{param_hash}"

@frappe.whitelist(allow_guest=False)
def execute():
    """
    API Endpoint for executing BigQuery Table Valued Functions.
    Expected payload:
    {
        "resource": "get_student_v1",
        "parameters": {"phone": "919999"},
        "bypass_cache": false,
        "mock_mode": false
    }
    """
    try:
        data = frappe.request.get_data(as_text=True)
        if data:
            payload = json.loads(data)
        else:
            payload = frappe.local.form_dict

        resource = payload.get("resource")
        parameters = payload.get("parameters", {})
        bypass_cache = frappe.utils.cint(payload.get("bypass_cache", 0))
        mock_mode = frappe.utils.cint(payload.get("mock_mode", 0))

        if not resource:
            frappe.local.response.http_status_code = 400
            return {"success": False, "error": "Missing 'resource' parameter."}

        settings = frappe.get_single("TAP BigQuery Settings")
        dataset_id = settings.dataset_id
        ttl = settings.default_cache_ttl or 300

        cache_key = get_cache_key(dataset_id, resource, parameters)

        if not bypass_cache and not mock_mode:
            cached_data = frappe.cache().get_value(cache_key)
            if cached_data:
                frappe.logger("bigquery").info(f"[BigQuery API] Cache HIT for {resource}")
                # cached_data is already a parsed python object since frappe.cache().get_value deserializes JSON by default
                return cached_data

        frappe.logger("bigquery").info(f"[BigQuery API] Executing {resource} (mock={mock_mode})")
        
        # Execute the TVF
        rows = execute_tvf(resource, parameters, mock_mode=bool(mock_mode))

        # Serialize rows safely handling datetimes
        safe_rows_json = json.dumps(rows, cls=JSONEncoderCustom)
        safe_rows = json.loads(safe_rows_json)

        response_payload = {
            "success": True,
            "data": safe_rows[0] if safe_rows else {},
            "rows": safe_rows
        }

        if not mock_mode:
            frappe.cache().set_value(cache_key, response_payload, expires_in_sec=ttl)

        return response_payload

    except frappe.exceptions.ValidationError as e:
        frappe.local.response.http_status_code = 400
        return {"success": False, "error": str(e)}
    
    except Exception as e:
        frappe.logger("bigquery").error(f"[BigQuery API] Unhandled Exception: {str(e)}")
        # Check if exception is from google cloud (NotFound, BadRequest)
        exc_name = type(e).__name__
        if exc_name == "NotFound":
            frappe.local.response.http_status_code = 404
            return {"success": False, "error": "Resource does not exist in API dataset."}
        elif exc_name == "BadRequest":
            frappe.local.response.http_status_code = 400
            return {"success": False, "error": "Invalid parameters passed to routine.", "details": str(e)}
        else:
            frappe.local.response.http_status_code = 500
            return {"success": False, "error": "Internal Server Error", "details": str(e)}
