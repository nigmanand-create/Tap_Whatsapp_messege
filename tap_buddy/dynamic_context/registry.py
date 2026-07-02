from typing import Optional, Dict
import frappe
from tap_buddy.dynamic_context.models import FlowConfig
from tap_buddy.dynamic_context.providers.config import BaseConfigProvider, FrappeDocTypeConfigProvider


class FlowRegistry:
    """
    Purpose: Single lookup and caching point for flow configurations.
    Responsibility: Intercepts flow requests, caching retrieved immutable FlowConfig objects in memory to avoid repetitive DB/disk lookups.
    Inputs: config_provider (Optional[BaseConfigProvider]).
    Outputs: Optional[FlowConfig] (Immutable).
    """
    def __init__(self, config_provider: Optional[BaseConfigProvider] = None):
        self.config_provider = config_provider or FrappeDocTypeConfigProvider()
        self._memory_cache: Dict[str, Optional[FlowConfig]] = {}

    def get_flow_config(self, flow_id: Optional[str] = None, category_fallback: Optional[str] = None) -> Optional[FlowConfig]:
        cache_key = f"{flow_id or ''}:{category_fallback or ''}"
        
        if cache_key in self._memory_cache:
            frappe.logger("dynamic_context").debug(f"[FlowRegistry HIT] {cache_key}")
            return self._memory_cache[cache_key]

        cfg = self.config_provider.get_flow_config(flow_id=flow_id, category_fallback=category_fallback)
        self._memory_cache[cache_key] = cfg
        
        if cfg:
            frappe.logger("dynamic_context").info(f"[FlowRegistry MISS -> RESOLVED] Loaded flow '{cfg.flow_id}' (Category: '{cfg.category}').")
        else:
            frappe.logger("dynamic_context").warning(f"[FlowRegistry MISS -> UNCONFIGURED] No mapping for flow_id='{flow_id}' category='{category_fallback}'.")
            
        return cfg
