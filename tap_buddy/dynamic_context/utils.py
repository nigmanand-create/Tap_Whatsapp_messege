import json
import datetime
import uuid
from typing import Dict, Any, Optional
from tap_buddy.services.bigquery_executor import JSONEncoderCustom


def get_payload_value(raw_payload: Dict[str, Any], key: str, default: Any = None) -> Any:
    """Standardized payload lookup: first checks root payload, falls back to payload['parameters']."""
    if not isinstance(raw_payload, dict):
        return default
    if key in raw_payload and raw_payload[key] is not None:
        return raw_payload[key]
    params = raw_payload.get("parameters")
    if isinstance(params, dict) and key in params and params[key] is not None:
        return params[key]
    if key in raw_payload:
        return raw_payload[key]
    if isinstance(params, dict) and key in params:
        return params[key]
    return default


def extract_params(raw_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts merged parameters dict: root payload overrides payload['parameters'], stripping internal metadata."""
    if not isinstance(raw_payload, dict):
        return {}
    internal_keys = ("secret", "contact", "parameters", "flow_id", "flow_category", "mock_mode", "bypass_cache", "request_id")
    params = {}
    raw_params = raw_payload.get("parameters")
    if isinstance(raw_params, dict):
        for k, v in raw_params.items():
            if k not in internal_keys:
                params[k] = v
    for k, v in raw_payload.items():
        if k not in internal_keys:
            if v is not None or k not in params:
                params[k] = v
    return params


def serialize_clean_json(data: dict) -> dict:
    """Serializes and deserializes dict using JSONEncoderCustom to safely convert BQ Decimal/datetime types."""
    if not data:
        return {}
    dumped = json.dumps(data, cls=JSONEncoderCustom)
    return json.loads(dumped)


def format_versioned_response(context_dict: dict, request_id: str = "unknown", source: str = "dynamic_context_engine") -> dict:
    """Formats standardized API response schema with versioning and correlation ID metadata."""
    ts = datetime.datetime.now(datetime.timezone.utc)
    clean_context = serialize_clean_json(context_dict)
    
    return {
        "success": True,
        "version": "v1",
        "request_id": request_id,
        "generated_at": ts.isoformat(),
        "source": source,
        "context": clean_context
    }


def format_error_response(error_code: str, message: str, request_id: str = "unknown", details: Optional[Dict[str, Any]] = None) -> dict:
    """Formats standardized API failure schema across all exception types."""
    return {
        "success": False,
        "version": "v1",
        "request_id": request_id,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {}
        }
    }
