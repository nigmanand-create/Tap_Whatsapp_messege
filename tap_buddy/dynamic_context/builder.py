import time
from typing import Dict, Any, Optional
import frappe
from tap_buddy.dynamic_context.models import ResolutionContext, FieldSource
from tap_buddy.dynamic_context.registry import FlowRegistry
from tap_buddy.dynamic_context.providers.data import BaseDataProvider, PayloadDataProvider, DefaultDataProvider, BigQueryDataProvider
from tap_buddy.dynamic_context.validators import PayloadValidator
from tap_buddy.dynamic_context.cache import IsolatedCacheWrapper
from tap_buddy.dynamic_context.exceptions import ConfigurationError, ValidationError
from tap_buddy.dynamic_context.metrics import MetricsCollector
from tap_buddy.dynamic_context.utils import get_payload_value, extract_params


class ContextBuilder:
    """
    Purpose: Flow context resolution orchestration engine.
    Responsibility: Coordinates pure field-driven context assembly across injected payload, default, and BigQuery data providers. 100% pure business logic (Dict -> Dict).
    Inputs: registry (FlowRegistry), payload_provider (BaseDataProvider), default_provider (BaseDataProvider), bigquery_provider (BaseDataProvider).
    Outputs: Resolved dictionary of flow context variables.
    """
    
    def __init__(
        self, 
        registry: Optional[FlowRegistry] = None,
        payload_provider: Optional[BaseDataProvider] = None,
        default_provider: Optional[BaseDataProvider] = None,
        bigquery_provider: Optional[BaseDataProvider] = None
    ):
        self.registry = registry or FlowRegistry()
        self.payload_provider = payload_provider or PayloadDataProvider()
        self.default_provider = default_provider or DefaultDataProvider()
        self.bigquery_provider = bigquery_provider or BigQueryDataProvider()

    def build_context(self, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        start_t = time.time()
        flow_id = str(get_payload_value(raw_payload, "flow_id", "") or "").strip()
        category = str(get_payload_value(raw_payload, "flow_category", "") or "").strip()
        tags = {"category": category or "unknown"}

        MetricsCollector.emit_counter("builder_invocations", tags=tags)

        flow_config = self.registry.get_flow_config(flow_id=flow_id or None, category_fallback=category or None)
        if not flow_config:
            frappe.logger("dynamic_context").warning(f"[ContextBuilder] No flow configuration for flow_id='{flow_id}' category='{category}'")
            MetricsCollector.emit_counter("flow_not_found", tags=tags)
            raise ConfigurationError(f"No Flow Config found for flow_id='{flow_id}' or category='{category}'.")

        try:
            PayloadValidator.validate_payload(flow_config, raw_payload)
        except ValidationError:
            MetricsCollector.emit_counter("validation_failures", tags=tags)
            raise

        contact = get_payload_value(raw_payload, "contact", {}) or {}
        if isinstance(contact, dict):
            phone = contact.get("phone") or get_payload_value(raw_payload, "phone") or "unknown"
        elif isinstance(contact, str):
            phone = get_payload_value(raw_payload, "phone") or (contact if contact != "@contact" else "unknown")
        else:
            phone = get_payload_value(raw_payload, "phone") or str(contact) or "unknown"
        mock_mode = bool(frappe.utils.cint(get_payload_value(raw_payload, "mock_mode", 0)))
        bypass_cache = bool(frappe.utils.cint(get_payload_value(raw_payload, "bypass_cache", 0))) or flow_config.bypass_cache

        params = extract_params(raw_payload)

        def _resolve_all_fields() -> Dict[str, Any]:
            res_ctx = ResolutionContext(
                flow_id=flow_config.flow_id,
                phone=phone,
                raw_payload=raw_payload,
                resolved_fields={},
                mock_mode=mock_mode
            )

            for field_cfg in flow_config.fields:
                if field_cfg.source == FieldSource.PAYLOAD:
                    val = self.payload_provider.resolve_field(field_cfg, res_ctx)
                elif field_cfg.source == FieldSource.DEFAULT:
                    val = self.default_provider.resolve_field(field_cfg, res_ctx)
                elif field_cfg.source == FieldSource.BIGQUERY:
                    val = self.bigquery_provider.resolve_field(field_cfg, res_ctx, routine_name=flow_config.bq_routine)
                else:
                    val = field_cfg.default_value

                res_ctx.resolved_fields[field_cfg.name] = val

            for k, v in params.items():
                if k not in res_ctx.resolved_fields:
                    res_ctx.resolved_fields[k] = v

            frappe.logger("dynamic_context").info(f"[ContextBuilder] Resolved {len(res_ctx.resolved_fields)} variables for flow '{flow_config.flow_id}'.")
            return res_ctx.resolved_fields

        resolved = IsolatedCacheWrapper.get_or_execute(
            flow_id=flow_config.flow_id,
            phone=phone,
            parameters=params,
            ttl=flow_config.cache_ttl,
            bypass_cache=bypass_cache,
            mock_mode=mock_mode,
            execute_fn=_resolve_all_fields
        )

        duration = (time.time() - start_t) * 1000.0
        MetricsCollector.emit_timing("builder_execution", duration, tags=tags)
        internal_keys = {"secret", "contact", "parameters", "flow_id", "flow_category", "mock_mode", "bypass_cache", "request_id"}
        return {k: v for k, v in (resolved or {}).items() if k not in internal_keys}
