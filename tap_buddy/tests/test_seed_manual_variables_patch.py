# -*- coding: utf-8 -*-
"""
Unit Tests for seed_manual_flow_variables Patch (Task B-02)
===========================================================
Verifies that the Frappe patch seeds manual/default flow variables for the six master
templates into Dynamic Context Flow Config and Dynamic Context Flow Field.

Proves:
1. Patch loads directly from flow_registry.json without duplicating config or sample content.
2. Pre-flight validation aborts migration if required flow/field keys are missing.
3. Patch is truly idempotent (running multiple times creates zero duplicate rows).
4. Every required manual variable exists after migration with safe/empty defaults.
5. Existing production records and custom modifications are preserved.
6. Only manual variables are seeded (no BigQuery/Glific/Webhook variables).
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch, mock_open
import pytest
import frappe

from tap_buddy.patches.seed_manual_flow_variables import execute as run_patch, validate_registry


@pytest.fixture(autouse=True)
def setup_frappe_local():
    sites_path = "sites" if os.path.exists("sites/tapbuddy.local") else "."
    frappe.init(site="tapbuddy.local", sites_path=sites_path)
    frappe.local.flags = frappe._dict()
    frappe.local.db = MagicMock()
    yield


class DummyFieldDoc:
    def __init__(self, field_name, field_source="Manual Default", default_value=None, is_required=0):
        self.field_name = field_name
        self.field_source = field_source
        self.default_value = default_value
        self.is_required = is_required


class DummyConfigDoc:
    def __init__(self, flow_id, flow_name="", flow_category="", is_active=1, bq_routine_name=None, cache_ttl=300, bypass_cache=0):
        self.flow_id = flow_id
        self.flow_name = flow_name
        self.flow_category = flow_category
        self.is_active = is_active
        self.bq_routine_name = bq_routine_name
        self.cache_ttl = cache_ttl
        self.bypass_cache = bypass_cache
        self.fields = []
        self.insert_calls = 0
        self.save_calls = 0

    @property
    def name(self):
        return self.flow_id

    @name.setter
    def name(self, val):
        self.flow_id = val

    def append(self, table_field, row_dict):
        if table_field == "fields":
            self.fields.append(
                DummyFieldDoc(
                    field_name=row_dict.get("field_name"),
                    field_source=row_dict.get("field_source", "Manual Default"),
                    default_value=row_dict.get("default_value"),
                    is_required=row_dict.get("is_required", 0),
                )
            )

    def insert(self, ignore_permissions=False):
        self.insert_calls += 1
        return self

    def save(self, ignore_permissions=False):
        self.save_calls += 1
        return self


class DummyRow:
    def __init__(self, name):
        self.name = name


class TestSeedManualFlowVariablesPatch(unittest.TestCase):
    def setUp(self):
        self.db_store = {}
        self.logger_mock = MagicMock()

    def _mock_get_all(self, doctype, filters=None, limit=None, **kwargs):
        if doctype == "Dynamic Context Flow Config":
            flow_id = filters.get("flow_id")
            if flow_id in self.db_store:
                return [DummyRow(self.db_store[flow_id].name)]
        return []

    def _mock_db_exists(self, doctype, name):
        if doctype == "Dynamic Context Flow Config":
            return name in self.db_store
        return False

    def _mock_get_doc(self, doctype, name):
        if doctype == "Dynamic Context Flow Config" and name in self.db_store:
            return self.db_store[name]
        raise ValueError(f"Doc {name} not found in db_store")

    def _mock_new_doc(self, doctype):
        if doctype == "Dynamic Context Flow Config":
            doc = DummyConfigDoc(flow_id="")
            orig_insert = doc.insert
            def insert_wrapper(ignore_permissions=False):
                self.db_store[doc.flow_id] = doc
                return orig_insert(ignore_permissions=ignore_permissions)
            doc.insert = insert_wrapper
            return doc
        raise ValueError(f"Unsupported doctype {doctype}")

    def test_registry_validation_missing_flow_key_aborts(self):
        """Test pre-flight validation aborts when a flow is missing required keys like cache_ttl."""
        invalid_data = {
            "flows": [
                {
                    "flow_id": "bad_flow",
                    "category": "test",
                    "fields": [],
                    "bypass_cache": False
                    # missing cache_ttl
                }
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            validate_registry(invalid_data, self.logger_mock)
        self.assertIn("missing required keys ['cache_ttl']", str(ctx.exception))
        self.logger_mock.error.assert_called_once()

    def test_registry_validation_missing_field_key_aborts(self):
        """Test pre-flight validation aborts when a field is missing required keys like source."""
        invalid_data = {
            "flows": [
                {
                    "flow_id": "test_flow",
                    "category": "test",
                    "cache_ttl": 300,
                    "bypass_cache": False,
                    "fields": [
                        {"name": "bad_field"}  # missing source
                    ]
                }
            ]
        }
        with self.assertRaises(ValueError) as ctx:
            validate_registry(invalid_data, self.logger_mock)
        self.assertIn("missing required keys ['source']", str(ctx.exception))
        self.logger_mock.error.assert_called_once()

    def test_seed_manual_variables_from_scratch_no_sample_content(self):
        """Test initial seeding into empty database creates all 6 master templates with empty configuration metadata."""
        with patch.object(frappe, "get_all", side_effect=self._mock_get_all), \
             patch.object(frappe.db, "exists", side_effect=self._mock_db_exists), \
             patch.object(frappe, "get_doc", side_effect=self._mock_get_doc), \
             patch.object(frappe, "new_doc", side_effect=self._mock_new_doc), \
             patch.object(frappe, "logger", return_value=self.logger_mock):
            
            run_patch()

        # 1. Verify exactly 6 master templates were created
        self.assertEqual(len(self.db_store), 6)
        self.assertIn("builtin_priority", self.db_store)
        self.assertIn("builtin_onboarding", self.db_store)
        self.assertIn("builtin_program_announcements", self.db_store)
        self.assertIn("builtin_engagement", self.db_store)
        self.assertIn("builtin_feedback", self.db_store)
        self.assertIn("builtin_celebratory", self.db_store)

        # 2. Verify builtin_priority manual variables have empty configuration metadata (no sample content)
        prio_doc = self.db_store["builtin_priority"]
        prio_fields = {f.field_name: f for f in prio_doc.fields}
        self.assertEqual(len(prio_fields), 10)
        self.assertIn("priority_level", prio_fields)
        self.assertEqual(prio_fields["priority_level"].default_value, "")  # Empty safe placeholder
        self.assertEqual(prio_fields["priority_level"].field_source, "Manual Default")
        self.assertEqual(prio_fields["priority_level"].is_required, 0)
        self.assertIn("target_zone", prio_fields)
        self.assertIn("target_district", prio_fields)
        self.assertIn("alert_title", prio_fields)
        self.assertIn("alert_message_body", prio_fields)
        self.assertIn("action_deadline", prio_fields)
        self.assertIn("coordinator_name", prio_fields)
        self.assertIn("support_helpline", prio_fields)
        self.assertIn("emergency_sop_document", prio_fields)
        self.assertIn("reference_image", prio_fields)

        # 3. Verify builtin_onboarding manual variables
        onb_doc = self.db_store["builtin_onboarding"]
        onb_fields = {f.field_name: f for f in onb_doc.fields}
        self.assertEqual(len(onb_fields), 6)
        self.assertIn("program_tier", onb_fields)
        self.assertIn("academic_year", onb_fields)
        self.assertIn("registration_deadline", onb_fields)
        self.assertIn("registration_portal_link", onb_fields)
        self.assertIn("excel_template_url", onb_fields)
        self.assertIn("setup_guide_pdf", onb_fields)
        # Verify NO BigQuery fields were seeded
        self.assertNotIn("total_registrations", onb_fields)
        self.assertNotIn("school_name", onb_fields)

        # 4. Verify total seeded field rows across all 6 templates
        total_rows = sum(len(doc.fields) for doc in self.db_store.values())
        self.assertEqual(total_rows, 47)  # 10 + 6 + 10 + 5 + 9 + 7

        # 5. Verify NO sample content exists across all 47 fields
        sample_keywords = ["Rajesh", "Bangalore", "South Zone", "http", "Zoom", "Dr. Anitha", "+91"]
        for doc in self.db_store.values():
            for field in doc.fields:
                val = str(field.default_value or "")
                for kw in sample_keywords:
                    self.assertNotIn(kw, val, f"Found sample content '{kw}' in field {field.field_name}!")

    def test_patch_is_idempotent_no_duplicate_rows(self):
        """Test running patch multiple times does not duplicate rows or trigger re-saves."""
        with patch.object(frappe, "get_all", side_effect=self._mock_get_all), \
             patch.object(frappe.db, "exists", side_effect=self._mock_db_exists), \
             patch.object(frappe, "get_doc", side_effect=self._mock_get_doc), \
             patch.object(frappe, "new_doc", side_effect=self._mock_new_doc), \
             patch.object(frappe, "logger", return_value=self.logger_mock):
            
            # First run
            run_patch()
            total_rows_1 = sum(len(doc.fields) for doc in self.db_store.values())
            self.assertEqual(total_rows_1, 47)

            # Reset save/insert counters
            for doc in self.db_store.values():
                doc.insert_calls = 0
                doc.save_calls = 0

            # Second run (duplicate execution)
            run_patch()
            total_rows_2 = sum(len(doc.fields) for doc in self.db_store.values())
            self.assertEqual(total_rows_2, 47)  # Exactly unchanged! No duplicate rows!

            # Verify neither insert nor save was called during second run
            for doc in self.db_store.values():
                self.assertEqual(doc.insert_calls, 0, f"Insert called on {doc.flow_id} during re-run!")
                self.assertEqual(doc.save_calls, 0, f"Save called on {doc.flow_id} during re-run when no changes occurred!")

    def test_preserve_existing_production_records(self):
        """Test that existing production records and custom field values/types are preserved."""
        # Pre-seed a production record for builtin_onboarding with custom settings and an existing BigQuery row
        prod_doc = DummyConfigDoc(
            flow_id="builtin_onboarding",
            flow_name="Custom Prod Onboarding",
            flow_category="onboarding",
            cache_ttl=900,
            bq_routine_name="custom_onboarding_routine"
        )
        # Add an existing BigQuery field
        prod_doc.fields.append(DummyFieldDoc("total_registrations", field_source="BigQuery"))
        # Add an existing manual field with a customized production default value
        prod_doc.fields.append(DummyFieldDoc("program_tier", field_source="Manual Default", default_value="Enterprise Edition"))
        self.db_store["builtin_onboarding"] = prod_doc

        with patch.object(frappe, "get_all", side_effect=self._mock_get_all), \
             patch.object(frappe.db, "exists", side_effect=self._mock_db_exists), \
             patch.object(frappe, "get_doc", side_effect=self._mock_get_doc), \
             patch.object(frappe, "new_doc", side_effect=self._mock_new_doc), \
             patch.object(frappe, "logger", return_value=self.logger_mock):
            
            run_patch()

        # 1. Verify production metadata was preserved
        self.assertEqual(prod_doc.flow_name, "Custom Prod Onboarding")
        self.assertEqual(prod_doc.cache_ttl, 900)
        self.assertEqual(prod_doc.bq_routine_name, "custom_onboarding_routine")

        # 2. Verify existing BigQuery field was preserved
        field_map = {f.field_name: f for f in prod_doc.fields}
        self.assertIn("total_registrations", field_map)
        self.assertEqual(field_map["total_registrations"].field_source, "BigQuery")

        # 3. Verify custom default value was preserved and not duplicated
        self.assertIn("program_tier", field_map)
        self.assertEqual(field_map["program_tier"].default_value, "Enterprise Edition")
        tier_count = sum(1 for f in prod_doc.fields if f.field_name == "program_tier")
        self.assertEqual(tier_count, 1)

        # 4. Verify remaining missing manual variables were appended
        self.assertIn("academic_year", field_map)
        self.assertIn("registration_deadline", field_map)
        self.assertIn("registration_portal_link", field_map)
        self.assertIn("excel_template_url", field_map)
        self.assertIn("setup_guide_pdf", field_map)
        self.assertEqual(len(prod_doc.fields), 7)  # 1 BQ field + 1 existing manual + 5 new manual


if __name__ == "__main__":
    unittest.main()
