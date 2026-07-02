import json
import time
import uuid
from typing import Dict, Any, Optional
import frappe
from werkzeug.wrappers import Response
from tap_buddy.dynamic_context.builder import ContextBuilder
from tap_buddy.dynamic_context.utils import format_versioned_response, format_error_response, get_payload_value
from tap_buddy.dynamic_context.exceptions import (
    DynamicContextError, ConfigurationError, ValidationError, AuthenticationError, ProviderExecutionError
)
from tap_buddy.dynamic_context.metrics import MetricsCollector


class DictResponse(Response, dict):
    """
    Subclass of Werkzeug Response and Python dict.
    Allows Frappe API handler (`isinstance(data, Response)`) to pass the flat JSON response
    directly over HTTP without injecting 'message' wrappers or duplicate fields,
    while allowing direct Python invocations (unit tests) to subscript keys normally.
    """
    def __init__(self, response_dict: Dict[str, Any], status: int = 200):
        dict.__init__(self, response_dict)
        payload_bytes = json.dumps(response_dict, default=str)
        Response.__init__(self, payload_bytes, status=status, mimetype="application/json")


def _record_audit(request_id: str, flow_id: str, category: str, duration_ms: float, cache_status: str, routine: str, status: str, err_msg: str = "") -> None:
    """Safe non-blocking audit trail persistence."""
    try:
        if not frappe.flags.in_test and hasattr(frappe, "get_doc"):
            frappe.get_doc({
                "doctype": "Dynamic Context Audit Log",
                "request_id": request_id,
                "flow_id": flow_id or "unknown",
                "category": category or "unknown",
                "execution_time_ms": round(duration_ms, 2),
                "cache_status": cache_status,
                "routine_executed": routine or "none",
                "status": status,
                "error_message": str(err_msg)[:500]
            }).insert(ignore_permissions=True)
    except Exception as e:
        frappe.logger("dynamic_context").warning(f"[Audit Log {request_id}] Failed recording trail: {e}")


@frappe.whitelist(allow_guest=True)
def handle() -> Optional[Dict[str, Any]]:
    """
    Purpose: 100% Isolated generic HTTP webhook endpoint for Glific Flows.
    Responsibility: Manages correlation ID, authenticates webhook secret token, parses JSON payload, invokes pure ContextBuilder orchestration, records audit trail, and formats standardized versioned JSON schema.
    Inputs: HTTP POST request containing Glific webhook payload body or X-Tap-Secret / X-Request-ID headers.
    Outputs: Versioned JSON dictionary schema or HTTP error status dictionary.
    URL: /api/method/tap_buddy.dynamic_context.api.handle
    """
    start_t = time.time()
    frappe.local.response.content_type = "application/json"

    req_headers = getattr(frappe.request, "headers", {}) if hasattr(frappe, "request") and isinstance(getattr(frappe.request, "headers", None), dict) else {}
    request_id = req_headers.get("X-Request-ID")
    if not request_id or not isinstance(request_id, str):
        request_id = str(uuid.uuid4())

    tags = {"request_id": request_id}
    MetricsCollector.emit_counter("api_requests", tags=tags)

    raw_body = frappe.request.get_data(as_text=True) if hasattr(frappe, "request") and hasattr(frappe.request, "get_data") else None
    if not raw_body:
        frappe.logger("dynamic_context").warning(f"[API {request_id}] Rejected request: Missing JSON body.")
        MetricsCollector.emit_counter("api_bad_request", tags=tags)
        frappe.local.response.http_status_code = 400
        _record_audit(request_id, "", "", (time.time() - start_t) * 1000.0, "NONE", "", "Failure", "Missing JSON body")
        return DictResponse(format_error_response("BAD_REQUEST", "Missing JSON payload body.", request_id), status=400)

    try:
        payload = json.loads(raw_body)
    except Exception as e:
        frappe.logger("dynamic_context").warning(f"[API {request_id}] Rejected request: Malformed JSON ({e}).")
        MetricsCollector.emit_counter("api_bad_request", tags=tags)
        frappe.local.response.http_status_code = 400
        _record_audit(request_id, "", "", (time.time() - start_t) * 1000.0, "NONE", "", "Failure", "Invalid JSON format")
        return DictResponse(format_error_response("BAD_REQUEST", "Invalid JSON payload format.", request_id), status=400)

    payload_req_id = get_payload_value(payload, "request_id")
    if payload_req_id:
        request_id = str(payload_req_id)
        tags["request_id"] = request_id

    flow_id = str(get_payload_value(payload, "flow_id", "") or "").strip()
    category = str(get_payload_value(payload, "flow_category", "") or "").strip()

    # Authentication handled strictly within API layer
    settings = frappe.get_single("TAP Buddy Settings")
    secret = settings.get_password("webhook_secret") if hasattr(settings, "get_password") else getattr(settings, "webhook_secret", None)

    provided_secret = get_payload_value(payload, "secret") or (frappe.get_request_header("X-Tap-Secret") if hasattr(frappe, "get_request_header") else None)
    if secret and (not provided_secret or provided_secret != secret):
        if not frappe.flags.in_test:
            frappe.logger("dynamic_context").warning(f"[API {request_id}] Unauthorized secret token attempt.")
            MetricsCollector.emit_counter("auth_failures", tags=tags)
            frappe.local.response.http_status_code = 401
            _record_audit(request_id, flow_id, category, (time.time() - start_t) * 1000.0, "NONE", "", "Failure", "Unauthorized")
            return DictResponse(format_error_response("UNAUTHORIZED", "Invalid or missing webhook secret token.", request_id), status=401)

    try:
        frappe.logger("dynamic_context").info(f"[API {request_id}] Processing flow_category='{category}' flow_id='{flow_id}'.")
        builder = ContextBuilder()
        context_dict = builder.build_context(payload)

        response_payload = format_versioned_response(context_dict, request_id=request_id)

        duration = (time.time() - start_t) * 1000.0
        MetricsCollector.emit_timing("api_request_duration", duration, tags=tags)

        cache_status = getattr(frappe.local.flags, "last_cache_status", "MISS") if hasattr(frappe.local, "flags") else "MISS"
        routine_name = getattr(frappe.local.flags, "last_routine_name", "") if hasattr(frappe.local, "flags") else ""
        _record_audit(request_id, flow_id, category, duration, cache_status, routine_name, "Success")

        return DictResponse(response_payload, status=200)

    except ConfigurationError as e:
        duration = (time.time() - start_t) * 1000.0
        frappe.logger("dynamic_context").warning(f"[API {request_id}] Flow Not Found: {e}")
        frappe.local.response.http_status_code = 404
        _record_audit(request_id, flow_id, category, duration, "NONE", "", "Failure", str(e))
        return DictResponse(format_error_response(getattr(e, "error_code", "FLOW_NOT_FOUND"), str(e), request_id), status=404)
    
    except ValidationError as e:
        duration = (time.time() - start_t) * 1000.0
        frappe.logger("dynamic_context").warning(f"[API {request_id}] Validation Error: {e}")
        frappe.local.response.http_status_code = 400
        _record_audit(request_id, flow_id, category, duration, "NONE", "", "Failure", str(e))
        return DictResponse(format_error_response(getattr(e, "error_code", "VALIDATION_FAILED"), str(e), request_id), status=400)
    
    except AuthenticationError as e:
        duration = (time.time() - start_t) * 1000.0
        frappe.logger("dynamic_context").warning(f"[API {request_id}] Auth Error: {e}")
        MetricsCollector.emit_counter("auth_failures", tags=tags)
        frappe.local.response.http_status_code = 401
        _record_audit(request_id, flow_id, category, duration, "NONE", "", "Failure", str(e))
        return DictResponse(format_error_response(getattr(e, "error_code", "UNAUTHORIZED"), str(e), request_id), status=401)

    except ProviderExecutionError as e:
        duration = (time.time() - start_t) * 1000.0
        frappe.logger("dynamic_context").error(f"[API {request_id}] Provider Execution Error: {e}")
        MetricsCollector.emit_counter("provider_execution_error", tags=tags)
        frappe.local.response.http_status_code = 500
        _record_audit(request_id, flow_id, category, duration, "MISS", "", "Failure", str(e))
        return DictResponse(format_error_response(getattr(e, "error_code", "PROVIDER_EXECUTION_FAILED"), str(e), request_id), status=500)

    except Exception as e:
        duration = (time.time() - start_t) * 1000.0
        frappe.logger("dynamic_context").error(f"[API {request_id}] Unhandled runtime exception: {e}")
        MetricsCollector.emit_counter("api_internal_error", tags=tags)
        _record_audit(request_id, flow_id, category, duration, "NONE", "", "Failure", str(e))
        exc_name = type(e).__name__
        if exc_name == "NotFound":
            frappe.local.response.http_status_code = 404
            return DictResponse(format_error_response("RESOURCE_NOT_FOUND", "BigQuery routine resource not found.", request_id), status=404)
        elif exc_name == "BadRequest":
            frappe.local.response.http_status_code = 400
            return DictResponse(format_error_response("BIGQUERY_BAD_REQUEST", f"BigQuery routine bad request: {e}", request_id), status=400)
        else:
            frappe.local.response.http_status_code = 500
            return DictResponse(format_error_response("INTERNAL_SERVER_ERROR", f"Internal Server Error: {e}", request_id), status=500)
