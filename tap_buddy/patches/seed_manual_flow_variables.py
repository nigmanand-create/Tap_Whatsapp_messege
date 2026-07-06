# -*- coding: utf-8 -*-
"""
Frappe Patch: Seed Manual Flow Variables
========================================
Idempotent patch to seed manual/default variables for the six master templates
into Dynamic Context Flow Config and Dynamic Context Flow Field DocTypes.

Single Source of Truth:
This patch loads variable definitions and configuration metadata directly from
`flow_registry.json`. No configuration or business/sample content is duplicated
or hardcoded within this patch.

Pre-flight Validation:
Validates that every flow contains required keys (`flow_id`, `category`, `fields`,
`cache_ttl`, `bypass_cache`) and every field contains required keys (`name`, `source`).
Aborts migration immediately with a clear error message if validation fails.

Preserves existing production records and prevents duplicate rows on re-run.
"""

import json
import os
import frappe


def validate_registry(registry_data, logger):
    """
    Validates registry structure and schema requirements before seeding data.
    Aborts migration by raising ValueError if any flow or field is malformed.
    """
    if not isinstance(registry_data, dict) or "flows" not in registry_data or not isinstance(registry_data["flows"], list):
        msg = "Registry validation failed: missing or invalid 'flows' list."
        logger.error(msg)
        raise ValueError(msg)

    required_flow_keys = {"flow_id", "category", "fields", "cache_ttl", "bypass_cache"}
    required_field_keys = {"name", "source"}

    for idx, template in enumerate(registry_data["flows"]):
        if not isinstance(template, dict):
            msg = f"Registry validation failed: flow at index {idx} is not a valid JSON object."
            logger.error(msg)
            raise ValueError(msg)

        missing_flow_keys = required_flow_keys - set(template.keys())
        if missing_flow_keys:
            flow_id_str = template.get("flow_id", f"index_{idx}")
            msg = f"Registry validation failed for flow '{flow_id_str}': missing required keys {sorted(list(missing_flow_keys))}."
            logger.error(msg)
            raise ValueError(msg)

        fields = template.get("fields")
        if not isinstance(fields, list):
            msg = f"Registry validation failed for flow '{template['flow_id']}': 'fields' must be a list."
            logger.error(msg)
            raise ValueError(msg)

        for f_idx, field_item in enumerate(fields):
            if not isinstance(field_item, dict):
                msg = f"Registry validation failed: field at index {f_idx} in flow '{template['flow_id']}' is not a valid JSON object."
                logger.error(msg)
                raise ValueError(msg)
            missing_field_keys = required_field_keys - set(field_item.keys())
            if missing_field_keys:
                field_name_str = field_item.get("name", f"index_{f_idx}")
                msg = f"Registry validation failed for field '{field_name_str}' in flow '{template['flow_id']}': missing required keys {sorted(list(missing_field_keys))}."
                logger.error(msg)
                raise ValueError(msg)


def execute():
    logger = frappe.logger("tap_buddy")
    logger.info("Starting seed_manual_flow_variables patch...")

    # Locate flow_registry.json as the single source of truth
    registry_path = None
    try:
        app_path = frappe.get_app_path("tap_buddy")
        registry_path = os.path.join(app_path, "dynamic_context", "flow_registry.json")
    except Exception:
        pass

    if not registry_path or not os.path.exists(registry_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        registry_path = os.path.join(base_dir, "dynamic_context", "flow_registry.json")

    if not os.path.exists(registry_path):
        logger.error("flow_registry.json not found at %s", registry_path)
        return

    with open(registry_path, "r", encoding="utf-8") as f:
        registry_data = json.load(f)

    # Perform pre-flight validation before any seeding
    validate_registry(registry_data, logger)

    for template in registry_data.get("flows", []):
        flow_id = template.get("flow_id")
        if not flow_id:
            continue

        existing_records = frappe.get_all(
            "Dynamic Context Flow Config",
            filters={"flow_id": flow_id},
            limit=1,
        )
        if existing_records:
            doc = frappe.get_doc("Dynamic Context Flow Config", existing_records[0].name)
            is_new = False
        elif frappe.db.exists("Dynamic Context Flow Config", flow_id):
            doc = frappe.get_doc("Dynamic Context Flow Config", flow_id)
            is_new = False
        else:
            doc = frappe.new_doc("Dynamic Context Flow Config")
            doc.flow_id = flow_id
            doc.flow_name = template.get("flow_name", flow_id)
            doc.flow_category = template.get("category", "")
            doc.is_active = 1
            if template.get("bq_routine"):
                doc.bq_routine_name = template["bq_routine"]
            doc.cache_ttl = int(template.get("cache_ttl", 300))
            doc.bypass_cache = int(template.get("bypass_cache", False))
            is_new = True

        existing_field_names = {getattr(f, "field_name", "") for f in getattr(doc, "fields", [])}
        modified = False

        for field_item in template.get("fields", []):
            src_str = str(field_item.get("source", "")).lower()
            if src_str in ("default", "manual default"):
                var_name = field_item.get("name")
                if var_name and var_name not in existing_field_names:
                    doc.append("fields", {
                        "field_name": var_name,
                        "field_source": "Manual Default",
                        "default_value": field_item.get("default_value", ""),
                        "is_required": int(field_item.get("required", 0)),
                    })
                    existing_field_names.add(var_name)
                    modified = True

        if is_new:
            doc.insert(ignore_permissions=True)
            logger.info("Inserted new Dynamic Context Flow Config for %s with manual variables", flow_id)
        elif modified:
            doc.save(ignore_permissions=True)
            logger.info("Updated existing Dynamic Context Flow Config for %s with missing manual variables", flow_id)
        else:
            logger.info("No changes needed for %s (manual variables already seeded)", flow_id)
