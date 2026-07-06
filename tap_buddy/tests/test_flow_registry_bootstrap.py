"""
Unit tests for flow_registry.json bootstrap configuration (Task B-01).

Validates:
- JSON syntax and readability
- Presence of required keys (flow_id, category, bq_routine, cache_ttl, bypass_cache)
- Registration of all 6 Master Template flows
- Standardized cache settings (cache_ttl: 300, bypass_cache: False)
- Exact matching between flow_id and category
- Naming alignment (e.g. school_name instead of school_names)
"""

import json
import os
import unittest


class TestFlowRegistryBootstrap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cls.registry_path = os.path.join(base_dir, "dynamic_context", "flow_registry.json")

    def test_registry_file_exists_and_valid_json(self):
        self.assertTrue(os.path.exists(self.registry_path), f"Registry missing at {self.registry_path}")
        with open(self.registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("flows", data)
        self.assertIsInstance(data["flows"], list)

    def test_required_keys_present_in_all_flows(self):
        with open(self.registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        required_keys = {"flow_id", "category", "bq_routine", "cache_ttl", "bypass_cache"}
        for flow in data["flows"]:
            missing = required_keys - set(flow.keys())
            self.assertEqual(len(missing), 0, f"Flow {flow.get('flow_id')} missing required keys: {missing}")

    def test_all_six_master_templates_configured(self):
        with open(self.registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        flows_by_id = {flow["flow_id"]: flow for flow in data["flows"]}
        expected_templates = {
            "builtin_priority": "priority",
            "builtin_onboarding": "onboarding",
            "builtin_program_announcements": "program_announcements",
            "builtin_engagement": "engagement",
            "builtin_feedback": "feedback",
            "builtin_celebratory": "celebratory",
        }

        for flow_id, expected_category in expected_templates.items():
            self.assertIn(flow_id, flows_by_id, f"Master template '{flow_id}' missing from registry")
            flow = flows_by_id[flow_id]
            self.assertEqual(flow["category"], expected_category, f"Mismatch in category for {flow_id}")
            self.assertEqual(flow["cache_ttl"], 300, f"cache_ttl must be 300 for {flow_id}")
            self.assertFalse(flow["bypass_cache"], f"bypass_cache must be false for {flow_id}")

    def test_naming_alignment_in_onboarding_fields(self):
        with open(self.registry_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        flows_by_id = {flow["flow_id"]: flow for flow in data["flows"]}
        onboarding = flows_by_id["builtin_onboarding"]
        field_names = [f["name"] for f in onboarding.get("fields", [])]

        self.assertIn("school_name", field_names, "onboarding must use school_name (singular)")
        self.assertNotIn("school_names", field_names, "onboarding must not use plural school_names")
