import concurrent.futures
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import frappe
from tap_buddy.dynamic_context.models import FieldConfig, ResolutionContext
from tap_buddy.dynamic_context.exceptions import ProviderExecutionError
from tap_buddy.dynamic_context.metrics import MetricsCollector
from tap_buddy.dynamic_context.utils import get_payload_value, extract_params


class BaseDataProvider(ABC):
    """
    Purpose: Abstract interface for field value retrieval.
    Responsibility: Defines the contract for resolving individual requested fields during flow execution.
    Inputs: field_config (FieldConfig), context (ResolutionContext), routine_name (Optional[str]).
    Outputs: Resolved field value (Any).
    """
    @abstractmethod
    def resolve_field(self, field_config: FieldConfig, context: ResolutionContext, routine_name: Optional[str] = None) -> Any:
        pass


class PayloadDataProvider(BaseDataProvider):
    """
    Purpose: Webhook payload field resolver.
    Responsibility: Extracts requested field values directly from incoming raw Glific webhook JSON.
    Inputs: field_config (FieldConfig), context (ResolutionContext), routine_name (Optional[str]).
    Outputs: Payload extracted value or default fallback.
    """
    def resolve_field(self, field_config: FieldConfig, context: ResolutionContext, routine_name: Optional[str] = None) -> Any:
        if field_config.name in context.raw_payload or (isinstance(context.raw_payload.get("parameters"), dict) and field_config.name in context.raw_payload["parameters"]):
            return get_payload_value(context.raw_payload, field_config.name)
        return field_config.default_value


class DefaultDataProvider(BaseDataProvider):
    """
    Purpose: Static default value resolver.
    Responsibility: Provides configured static fallback defaults when incoming payload values are missing or empty.
    Inputs: field_config (FieldConfig), context (ResolutionContext), routine_name (Optional[str]).
    Outputs: Non-empty payload value or configured static default.
    """
    def resolve_field(self, field_config: FieldConfig, context: ResolutionContext, routine_name: Optional[str] = None) -> Any:
        val = get_payload_value(context.raw_payload, field_config.name)
        if val is not None and str(val).strip() != "":
            return val
        return field_config.default_value


class BigQueryDataProvider(BaseDataProvider):
    """
    Purpose: BigQuery Table-Valued Function (TVF) data resolver.
    Responsibility: Executes BigQuery TVFs via existing `execute_tvf` service with configurable timeout protection, batching row caching request-wide.
    Inputs: field_config (FieldConfig), context (ResolutionContext), routine_name (Optional[str]).
    Outputs: Column value extracted from BigQuery row dict or default fallback.
    """
    def __init__(self):
        self._routine_results: Dict[str, Dict[str, Any]] = {}

    def resolve_field(self, field_config: FieldConfig, context: ResolutionContext, routine_name: Optional[str] = None) -> Any:
        if not routine_name:
            return field_config.default_value

        if hasattr(frappe.local, "flags"):
            frappe.local.flags.last_routine_name = routine_name

        cache_key = f"{routine_name}:{context.phone}:{context.mock_mode}"

        if cache_key not in self._routine_results:
            timeout_sec = getattr(frappe.conf, "bq_timeout_sec", 15) or 15
            start_t = time.time()
            try:
                # Strictly reuses existing production BigQuery service. No duplicated client or auth logic.
                from tap_buddy.services.bigquery_executor import execute_tvf
                params = extract_params(context.raw_payload)
                params["phone"] = context.phone
                
                frappe.logger("dynamic_context").info(f"[BigQueryProvider] Executing TVF routine '{routine_name}' for phone '{context.phone}' (Timeout: {timeout_sec}s).")
                
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(execute_tvf, routine_name, params, mock_mode=context.mock_mode)
                    rows = future.result(timeout=timeout_sec)
                
                duration = (time.time() - start_t) * 1000.0
                MetricsCollector.emit_counter("bq_execution", tags={"routine": routine_name})
                MetricsCollector.emit_timing("bq_execution", duration, tags={"routine": routine_name})
                
                self._routine_results[cache_key] = rows[0] if rows else {}
                frappe.logger("dynamic_context").debug(f"[BigQueryProvider] Cached TVF row for key: {cache_key} ({round(duration, 1)}ms)")
            except concurrent.futures.TimeoutError as e:
                msg = f"BigQuery execution timed out after {timeout_sec}s for routine '{routine_name}'."
                frappe.logger("dynamic_context").error(f"[BigQueryProvider] {msg}")
                MetricsCollector.emit_counter("bq_timeout", tags={"routine": routine_name})
                raise ProviderExecutionError(msg) from e
            except Exception as e:
                frappe.logger("dynamic_context").error(f"[BigQueryProvider] TVF execution failed for '{routine_name}': {e}")
                MetricsCollector.emit_counter("bq_error", tags={"routine": routine_name})
                raise ProviderExecutionError(f"BigQuery execution failed for routine '{routine_name}': {str(e)}") from e

        row_data = self._routine_results[cache_key]
        if field_config.name in row_data:
            return row_data[field_config.name]

        return field_config.default_value
