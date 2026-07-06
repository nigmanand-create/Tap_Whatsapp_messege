# -*- coding: utf-8 -*-
"""
Unit Tests for Flow Parameter Override Schema (Task C-01)
=========================================================
Verifies that TAP Campaign and Recurring Campaign Template DocTypes have been properly
extended with the `flow_custom_parameters` JSON code field and depends-on UI rules.

Proves:
1. Field `flow_custom_parameters` exists in both DocTypes with fieldtype 'Code' and options 'JSON'.
2. Field depends_on rule is set to `eval:doc.campaign_type == 'Flow'`.
3. Backend validation cleanly accepts valid JSON override parameters.
4. Backend validation cleanly throws an error when malformed JSON is supplied.
"""

import json
import os
import unittest
from unittest.mock import MagicMock, patch
import pytest
import frappe

from tap_buddy.tap_buddy.doctype.tap_campaign.tap_campaign import TAPCampaign
from tap_buddy.tap_buddy.doctype.recurring_campaign_template.recurring_campaign_template import RecurringCampaignTemplate


def dummy_throw(msg, *args, **kwargs):
    raise ValueError(msg)


class DummyTAPCampaign(TAPCampaign):
    def __init__(self, **kwargs):
        self.name = "CAMP-001"
        self.campaign_name = kwargs.get("campaign_name", "Test Campaign")
        self.targeting_type = kwargs.get("targeting_type", "Single School")
        self.school_name = kwargs.get("school_name", "SCH-001")
        self.campaign_type = kwargs.get("campaign_type", "Flow")
        self.glific_flow = kwargs.get("glific_flow", "flow_123")
        self.template = kwargs.get("template", None)
        self.send_date = kwargs.get("send_date", "2026-07-03 09:00:00")
        self.flow_custom_parameters = kwargs.get("flow_custom_parameters", None)


class DummyRecurringTemplate(RecurringCampaignTemplate):
    def __init__(self, **kwargs):
        self.name = "RCT-001"
        self.template_name = kwargs.get("template_name", "Test Template")
        self.start_date = kwargs.get("start_date", "2026-07-03 09:00:00")
        self.end_date = kwargs.get("end_date", None)
        self.targeting_type = kwargs.get("targeting_type", "Single School")
        self.school_name = kwargs.get("school_name", "SCH-001")
        self.campaign_type = kwargs.get("campaign_type", "Flow")
        self.glific_flow = kwargs.get("glific_flow", "flow_123")
        self.template = kwargs.get("template", None)
        self.recurrence_type = kwargs.get("recurrence_type", "Daily")
        self.cron_expression = kwargs.get("cron_expression", None)
        self.flow_custom_parameters = kwargs.get("flow_custom_parameters", None)


class TestCampaignFlowOverrideSchema(unittest.TestCase):
    def setUp(self):
        self.orig_throw = frappe.throw
        frappe.throw = dummy_throw

    def tearDown(self):
        frappe.throw = self.orig_throw

    def _load_doctype_json(self, doctype_folder, json_filename):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        json_path = os.path.join(base_dir, "tap_buddy", "doctype", doctype_folder, json_filename)
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_tap_campaign_schema_contains_flow_custom_parameters(self):
        """Verify tap_campaign.json defines flow_custom_parameters with correct UI depends_on."""
        schema = self._load_doctype_json("tap_campaign", "tap_campaign.json")
        fields = {f.get("fieldname"): f for f in schema.get("fields", [])}
        
        self.assertIn("flow_custom_parameters", fields)
        field = fields["flow_custom_parameters"]
        self.assertEqual(field.get("fieldtype"), "Code")
        self.assertEqual(field.get("options"), "JSON")
        self.assertEqual(field.get("label"), "Flow Custom Parameters (JSON)")
        self.assertEqual(field.get("depends_on"), "eval:doc.campaign_type == 'Flow'")

    def test_recurring_campaign_template_schema_contains_flow_custom_parameters(self):
        """Verify recurring_campaign_template.json defines flow_custom_parameters with correct UI depends_on."""
        schema = self._load_doctype_json("recurring_campaign_template", "recurring_campaign_template.json")
        fields = {f.get("fieldname"): f for f in schema.get("fields", [])}
        
        self.assertIn("flow_custom_parameters", fields)
        field = fields["flow_custom_parameters"]
        self.assertEqual(field.get("fieldtype"), "Code")
        self.assertEqual(field.get("options"), "JSON")
        self.assertEqual(field.get("label"), "Flow Custom Parameters (JSON)")
        self.assertEqual(field.get("depends_on"), "eval:doc.campaign_type == 'Flow'")

    def test_tap_campaign_validate_valid_json(self):
        """Verify backend validation passes when flow_custom_parameters is valid JSON."""
        doc = DummyTAPCampaign(flow_custom_parameters='{"meeting_link": "https://zoom.us/test", "tier": "Gold"}')
        try:
            doc.validate()
        except ValueError as e:
            self.fail(f"validate() raised ValueError unexpectedly for valid JSON: {e}")

    def test_tap_campaign_validate_invalid_json(self):
        """Verify backend validation throws error when flow_custom_parameters is malformed JSON."""
        doc = DummyTAPCampaign(flow_custom_parameters='{meeting_link: "no quotes around key",}')
        with self.assertRaises(ValueError) as ctx:
            doc.validate()
        self.assertIn("Flow Custom Parameters must be valid JSON", str(ctx.exception))

    def test_recurring_template_validate_valid_json(self):
        """Verify template backend validation passes when flow_custom_parameters is valid JSON."""
        doc = DummyRecurringTemplate(flow_custom_parameters='{"alert_title": "Urgent Alert", "deadline": "2026-07-10"}')
        try:
            doc.validate()
        except ValueError as e:
            self.fail(f"validate() raised ValueError unexpectedly for valid JSON: {e}")

    def test_recurring_template_validate_invalid_json(self):
        """Verify template backend validation throws error when flow_custom_parameters is malformed JSON."""
        doc = DummyRecurringTemplate(flow_custom_parameters='{"broken_json": ')
        with self.assertRaises(ValueError) as ctx:
            doc.validate()
        self.assertIn("Flow Custom Parameters must be valid JSON", str(ctx.exception))

    def test_validate_flow_custom_parameters_types(self):
        """Verify strict JSON object (dict) validation across all required data types."""
        from tap_buddy.utils.validation import validate_flow_custom_parameters

        # 1. Allowed: {}
        try:
            validate_flow_custom_parameters("{}")
        except ValueError as e:
            self.fail(f"validate_flow_custom_parameters('{{}}') failed unexpectedly: {e}")

        # 2. Allowed: {"meeting_link": "..."}
        try:
            validate_flow_custom_parameters('{"meeting_link": "https://zoom.us/test"}')
        except ValueError as e:
            self.fail(f"validate_flow_custom_parameters('{{\"meeting_link\": ...}}') failed unexpectedly: {e}")

        # 3. Rejected: [] (Array)
        with self.assertRaises(ValueError) as ctx:
            validate_flow_custom_parameters("[]")
        self.assertIn("must be a JSON object (dict)", str(ctx.exception))

        # 4. Rejected: "abc" (String)
        with self.assertRaises(ValueError) as ctx:
            validate_flow_custom_parameters('"abc"')
        self.assertIn("must be a JSON object (dict)", str(ctx.exception))

        # 5. Rejected: 123 (Number)
        with self.assertRaises(ValueError) as ctx:
            validate_flow_custom_parameters("123")
        self.assertIn("must be a JSON object (dict)", str(ctx.exception))

        # 6. Rejected: true (Boolean)
        with self.assertRaises(ValueError) as ctx:
            validate_flow_custom_parameters("true")
        self.assertIn("must be a JSON object (dict)", str(ctx.exception))

        # 7. Rejected: null (JSON null string)
        with self.assertRaises(ValueError) as ctx:
            validate_flow_custom_parameters("null")
        self.assertIn("must be a JSON object (dict)", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
