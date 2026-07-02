import re
from typing import Dict, Any
import frappe
from tap_buddy.dynamic_context.models import FlowConfig, FieldSource
from tap_buddy.dynamic_context.exceptions import ValidationError
from tap_buddy.dynamic_context.utils import get_payload_value


class PayloadValidator:
    """
    Purpose: Incoming webhook payload verification engine.
    Responsibility: Enforces mandatory field presence and regex pattern matching constraints before ContextBuilder resolves fields.
    Inputs: flow_config (FlowConfig), raw_payload (Dict[str, Any]).
    Outputs: None (Raises ValidationError on constraint breach).
    """
    
    @staticmethod
    def validate_payload(flow_config: FlowConfig, raw_payload: Dict[str, Any]) -> None:
        if not raw_payload:
            frappe.logger("dynamic_context").warning("[PayloadValidator] Rejected empty payload dictionary.")
            raise ValidationError("Incoming webhook payload is empty.")

        for field_cfg in flow_config.fields:
            val = get_payload_value(raw_payload, field_cfg.name)
            
            if field_cfg.required and (val is None or str(val).strip() == ""):
                if field_cfg.source == FieldSource.PAYLOAD and field_cfg.default_value is None:
                    msg = f"Required input field '{field_cfg.name}' is missing in webhook payload."
                    frappe.logger("dynamic_context").warning(f"[PayloadValidator] {msg}")
                    raise ValidationError(msg)

            if val is not None and str(val).strip() != "" and field_cfg.validation_regex:
                pattern = str(field_cfg.validation_regex)
                try:
                    if not re.match(pattern, str(val)):
                        msg = f"Value '{val}' for field '{field_cfg.name}' failed regex validation '{pattern}'."
                        frappe.logger("dynamic_context").warning(f"[PayloadValidator] {msg}")
                        raise ValidationError(msg)
                except re.error as e:
                    msg = f"Invalid validation regex '{pattern}' configured for field '{field_cfg.name}': {e}"
                    frappe.logger("dynamic_context").error(f"[PayloadValidator] {msg}")
                    raise ValidationError(msg) from e
                    
        frappe.logger("dynamic_context").debug(f"[PayloadValidator] Successfully validated payload for flow '{flow_config.flow_id}'.")
