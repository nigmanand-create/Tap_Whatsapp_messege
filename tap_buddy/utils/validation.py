# -*- coding: utf-8 -*-
"""
Shared Validation Helpers
=========================
Contains reusable validation functions for DocTypes and Services.
"""
import json
import frappe


def validate_flow_custom_parameters(value):
    """
    Validates that the provided flow_custom_parameters value is a valid JSON object (dict).
    Rejects arrays, strings, numbers, booleans, and nulls.
    Allows None or empty strings (representing unassigned parameter overrides).
    """
    if value is None:
        return
    if isinstance(value, str) and not value.strip():
        return

    if isinstance(value, dict):
        return

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except Exception:
            frappe.throw("Flow Custom Parameters must be valid JSON")
    else:
        parsed = value

    if not isinstance(parsed, dict):
        frappe.throw("Flow Custom Parameters must be a JSON object (dict)")
