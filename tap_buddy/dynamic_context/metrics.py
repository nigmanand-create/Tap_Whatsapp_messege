import json
from typing import Dict, Any, Optional
import frappe


class MetricsCollector:
    """
    Purpose: Standardized observability and telemetry collection.
    Responsibility: Emits structured JSON log metrics for request counters, failure rates, cache performance, and execution durations.
    Inputs: metric_name (str), value (Union[int, float]), tags (Dict[str, str]).
    Outputs: Structured JSON metrics log record.
    """
    
    @staticmethod
    def emit_counter(metric_name: str, value: int = 1, tags: Optional[Dict[str, str]] = None) -> None:
        clean_tags = {str(k): str(v) for k, v in (tags or {}).items()}
        telemetry = {
            "metric_type": "counter",
            "metric_name": f"dynamic_context_{metric_name}",
            "value": value,
            "tags": clean_tags
        }
        frappe.logger("dynamic_context_metrics").info(json.dumps(telemetry, sort_keys=True))

    @staticmethod
    def emit_timing(metric_name: str, duration_ms: float, tags: Optional[Dict[str, str]] = None) -> None:
        clean_tags = {str(k): str(v) for k, v in (tags or {}).items()}
        telemetry = {
            "metric_type": "histogram",
            "metric_name": f"dynamic_context_{metric_name}_duration_ms",
            "value": round(duration_ms, 2),
            "tags": clean_tags
        }
        frappe.logger("dynamic_context_metrics").info(json.dumps(telemetry, sort_keys=True))
