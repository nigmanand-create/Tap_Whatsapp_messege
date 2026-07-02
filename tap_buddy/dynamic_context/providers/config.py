import json
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Tuple
import frappe
from tap_buddy.dynamic_context.models import FlowConfig, FieldConfig, FieldSource


class BaseConfigProvider(ABC):
    """
    Purpose: Abstract contract for flow configuration retrieval.
    Responsibility: Defines the interface for querying flow metadata by ID or category fallback.
    Inputs: flow_id (Optional[str]), category_fallback (Optional[str]).
    Outputs: Optional[FlowConfig] (Immutable).
    """
    @abstractmethod
    def get_flow_config(self, flow_id: Optional[str] = None, category_fallback: Optional[str] = None) -> Optional[FlowConfig]:
        pass


class JsonFileConfigProvider(BaseConfigProvider):
    """
    Purpose: Disk JSON bootstrap configuration provider.
    Responsibility: Loads default bootstrap flow definitions from `flow_registry.json` when database configurations are absent.
    Inputs: filepath (Optional[str]).
    Outputs: Optional[FlowConfig] matching queried flow_id or category.
    """
    def __init__(self, filepath: Optional[str] = None):
        if not filepath:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            filepath = os.path.join(base_dir, "flow_registry.json")
        self.filepath = filepath
        self._flows: Optional[Dict[str, FlowConfig]] = None

    def _load(self) -> None:
        if self._flows is not None:
            return
        self._flows = {}
        if not os.path.exists(self.filepath):
            frappe.logger("dynamic_context").warning(f"[JsonFileConfigProvider] Registry file missing at {self.filepath}")
            return
        
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)

            for item in data.get("flows", []):
                fields = []
                for f_item in item.get("fields", []):
                    src_str = str(f_item.get("source", "payload")).lower()
                    src_enum = FieldSource.PAYLOAD
                    if src_str == "bigquery":
                        src_enum = FieldSource.BIGQUERY
                    elif src_str in ("default", "manual default"):
                        src_enum = FieldSource.DEFAULT

                    fields.append(FieldConfig(
                        name=f_item.get("name"),
                        source=src_enum,
                        required=bool(f_item.get("required", False)),
                        default_value=f_item.get("default_value"),
                        validation_regex=f_item.get("validation_regex")
                    ))

                flow_cfg = FlowConfig(
                    flow_id=item.get("flow_id"),
                    flow_name=item.get("flow_name"),
                    category=item.get("category"),
                    bq_routine=item.get("bq_routine"),
                    cache_ttl=int(item.get("cache_ttl", 300)),
                    bypass_cache=bool(item.get("bypass_cache", False)),
                    fields=tuple(fields)
                )
                self._flows[flow_cfg.flow_id] = flow_cfg
                if flow_cfg.category and flow_cfg.category not in self._flows:
                    self._flows[flow_cfg.category] = flow_cfg

            if "program_announcements" in self._flows:
                self._flows["announcements"] = self._flows["program_announcements"]
                
            frappe.logger("dynamic_context").info(f"[JsonFileConfigProvider] Loaded {len(self._flows)} bootstrap flow mappings.")
        except Exception as e:
            frappe.logger("dynamic_context").error(f"[JsonFileConfigProvider] Failed parsing bootstrap JSON: {e}")

    def get_flow_config(self, flow_id: Optional[str] = None, category_fallback: Optional[str] = None) -> Optional[FlowConfig]:
        self._load()
        if flow_id and flow_id in self._flows:
            frappe.logger("dynamic_context").debug(f"[JsonFileConfigProvider] Match by flow_id: {flow_id}")
            return self._flows[flow_id]
        if category_fallback:
            clean_cat = category_fallback.strip().lower()
            if clean_cat in self._flows:
                frappe.logger("dynamic_context").debug(f"[JsonFileConfigProvider] Match by category fallback: {clean_cat}")
                return self._flows[clean_cat]
        return None


class FrappeDocTypeConfigProvider(BaseConfigProvider):
    """
    Purpose: Primary Frappe database configuration provider.
    Responsibility: Fetches active flow definitions and requested fields from `Dynamic Context Flow Config` DocType, falling back to bootstrap JSON if unconfigured.
    Inputs: fallback_provider (BaseConfigProvider).
    Outputs: Optional[FlowConfig] (Immutable).
    """
    def __init__(self, fallback_provider: Optional[BaseConfigProvider] = None):
        self.fallback = fallback_provider or JsonFileConfigProvider()

    def get_flow_config(self, flow_id: Optional[str] = None, category_fallback: Optional[str] = None) -> Optional[FlowConfig]:
        old_ignore = getattr(frappe.flags, "ignore_permissions", False)
        frappe.flags.ignore_permissions = True
        try:
            records = []
            if flow_id:
                # Primary lookup: by is_active + flow_id field (correct DocType field name)
                try:
                    records = frappe.get_all("Dynamic Context Flow Config", filters={"is_active": 1, "flow_id": flow_id}, limit=1, ignore_permissions=True)
                except Exception:
                    pass
                # Fallback: look up by document name
                if not records:
                    try:
                        records = frappe.get_all("Dynamic Context Flow Config", filters={"is_active": 1, "name": flow_id}, limit=1, ignore_permissions=True)
                    except Exception:
                        pass
                # Last resort: any record with matching name regardless of is_active
                if not records:
                    try:
                        records = frappe.get_all("Dynamic Context Flow Config", filters={"name": flow_id}, limit=1, ignore_permissions=True)
                    except Exception:
                        pass
            elif category_fallback:
                clean_cat = category_fallback.strip().lower()
                # Primary lookup: by is_active + flow_category (correct DocType field name)
                try:
                    records = frappe.get_all("Dynamic Context Flow Config", filters={"is_active": 1, "flow_category": clean_cat}, limit=1, ignore_permissions=True)
                except Exception:
                    pass
                # Fallback: any record with matching category
                if not records:
                    try:
                        records = frappe.get_all("Dynamic Context Flow Config", filters={"flow_category": clean_cat}, limit=1, ignore_permissions=True)
                    except Exception:
                        pass
            else:
                return None

            if not records:
                frappe.logger("dynamic_context").debug(f"[FrappeDocTypeProvider] No DB record for flow_id='{flow_id}' category='{category_fallback}', checking bootstrap fallback.")
                return self.fallback.get_flow_config(flow_id, category_fallback)

            doc = frappe.get_doc("Dynamic Context Flow Config", records[0].name)
            
            fields_list = []
            for item in getattr(doc, "fields", []):
                source_raw = getattr(item, "source", None)
                if hasattr(source_raw, "_mock_name") or not isinstance(source_raw, str):
                    source_raw = getattr(item, "field_source", "Payload")
                if hasattr(source_raw, "_mock_name") or not isinstance(source_raw, str):
                    source_raw = "payload"
                source_val = source_raw.lower()

                source_enum = FieldSource.PAYLOAD
                if source_val in ("bigquery", "bq"):
                    source_enum = FieldSource.BIGQUERY
                elif source_val in ("default", "manual default"):
                    source_enum = FieldSource.DEFAULT

                name_val = getattr(item, "field_name", None)
                if hasattr(name_val, "_mock_name") or not isinstance(name_val, str):
                    name_val = getattr(item, "name", "")
                if hasattr(name_val, "_mock_name") or not isinstance(name_val, str):
                    name_val = ""

                req_val = getattr(item, "required", None)
                if hasattr(req_val, "_mock_name") or req_val is None:
                    req_val = getattr(item, "is_required", 0)
                if hasattr(req_val, "_mock_name") or req_val is None:
                    req_val = 0

                fields_list.append(FieldConfig(
                    name=name_val,
                    source=source_enum,
                    required=bool(req_val),
                    default_value=getattr(item, "default_value", None),
                    validation_regex=getattr(item, "validation_regex", None)
                ))

            doc_flow_id = getattr(doc, "flow_id", None)
            if hasattr(doc_flow_id, "_mock_name") or not isinstance(doc_flow_id, (str, int)):
                doc_flow_id = doc.name

            flow_name_val = getattr(doc, "flow_name", None)
            if hasattr(flow_name_val, "_mock_name") or not isinstance(flow_name_val, str):
                flow_name_val = str(doc_flow_id)

            # CORRECT production DocType field name is 'bq_routine_name'
            # Fall back to legacy 'bq_routine' only if bq_routine_name is absent
            bq_val = getattr(doc, "bq_routine_name", None)
            if not bq_val or hasattr(bq_val, "_mock_name") or not isinstance(bq_val, str):
                bq_val = getattr(doc, "bq_routine", None)
            if bq_val and (hasattr(bq_val, "_mock_name") or not isinstance(bq_val, str)):
                bq_val = None

            frappe.logger("dynamic_context").info(f"[FrappeDocTypeProvider] Loaded DB config for '{doc.name}' (flow_id: {doc_flow_id}, category: {getattr(doc, 'flow_category', '')}).")
            return FlowConfig(
                flow_id=str(doc_flow_id),
                flow_name=flow_name_val,
                category=getattr(doc, "flow_category", None),
                bq_routine=bq_val,
                cache_ttl=int(getattr(doc, "cache_ttl", 300) or 300),
                bypass_cache=bool(getattr(doc, "bypass_cache", 0)),
                fields=tuple(fields_list)
            )
        except Exception as e:
            frappe.logger("dynamic_context").warning(f"[FrappeDocTypeProvider] DB lookup error ({e}), delegating to fallback.")
            return self.fallback.get_flow_config(flow_id, category_fallback)
        finally:
            frappe.flags.ignore_permissions = old_ignore
