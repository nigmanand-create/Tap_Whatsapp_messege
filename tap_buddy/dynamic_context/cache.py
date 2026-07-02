import hashlib
import json
from typing import Callable, Any, Dict
import frappe
from tap_buddy.dynamic_context.metrics import MetricsCollector


class IsolatedCacheWrapper:
    """
    Purpose: SHA-256 deterministic caching wrapper.
    Responsibility: Generates collision-resistant cache keys, checks Frappe Redis cache, enforces TTLs, and emits cache telemetry metrics.
    Inputs: flow_id (str), phone (str), parameters (dict), ttl (int), bypass_cache (bool), mock_mode (bool), execute_fn (Callable).
    Outputs: Computed or cached context dictionary (Dict[str, Any]).
    """
    
    @staticmethod
    def generate_cache_key(flow_id: str, phone: str, parameters: dict, mock_mode: bool = False) -> str:
        param_str = json.dumps(parameters or {}, sort_keys=True)
        param_hash = hashlib.sha256(param_str.encode("utf-8")).hexdigest()
        return f"dyn_ctx:v1:{flow_id}:{phone}:{param_hash}:{mock_mode}"

    @classmethod
    def get_or_execute(
        cls, 
        flow_id: str, 
        phone: str, 
        parameters: dict, 
        ttl: int, 
        bypass_cache: bool, 
        mock_mode: bool, 
        execute_fn: Callable[[], Dict[str, Any]]
    ) -> Dict[str, Any]:
        tags = {"flow_id": flow_id}
        if hasattr(frappe.local, "flags"):
            frappe.local.flags.last_cache_status = "BYPASS" if bypass_cache else "MISS"

        if bypass_cache:
            frappe.logger("dynamic_context").info(f"[Cache BYPASSED] flow_id='{flow_id}' phone='{phone}' (Bypass: {bypass_cache}).")
            MetricsCollector.emit_counter("cache_bypass", tags=tags)
            return execute_fn()

        cache_key = cls.generate_cache_key(flow_id, phone, parameters, mock_mode)
        try:
            cached = frappe.cache().get_value(cache_key)
            if cached:
                frappe.logger("dynamic_context").info(f"[Cache HIT] {cache_key}")
                MetricsCollector.emit_counter("cache_hit", tags=tags)
                if hasattr(frappe.local, "flags"):
                    frappe.local.flags.last_cache_status = "HIT"
                return cached
            else:
                frappe.logger("dynamic_context").info(f"[Cache MISS] {cache_key}")
                MetricsCollector.emit_counter("cache_miss", tags=tags)
        except Exception as e:
            frappe.logger("dynamic_context").warning(f"[Cache READ ERROR] Failed fetching {cache_key}: {e}")

        result = execute_fn()
        
        if result:
            try:
                frappe.cache().set_value(cache_key, result, expires_in_sec=ttl)
                frappe.logger("dynamic_context").debug(f"[Cache STORED] Stored {cache_key} with TTL {ttl}s.")
            except Exception as e:
                frappe.logger("dynamic_context").warning(f"[Cache WRITE ERROR] Failed storing {cache_key}: {e}")

        return result
