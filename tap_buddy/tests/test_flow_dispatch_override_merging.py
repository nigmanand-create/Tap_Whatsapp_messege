# -*- coding: utf-8 -*-
"""
Unit Tests for Flow Dispatch Parameter Binding (Task C-02)
==========================================================
Verifies that custom parameters defined on a TAP Campaign are parsed,
merged with standard recipient school context, and passed as `default_results`
into Glific flow dispatches. Also verifies resilience against malformed JSON,
handling of null/empty/nested/unknown keys, and WA Group Flow behavior.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import sys

# Set up clean mocks for frappe environment
try:
    import frappe
    import frappe.utils
    import frappe.model
    import frappe.model.document
except ImportError:
    pass

if "frappe" in sys.modules and not isinstance(sys.modules["frappe"], MagicMock):
    mock_frappe = sys.modules["frappe"]
else:
    mock_frappe = MagicMock()
    sys.modules["frappe"] = mock_frappe

if "frappe.utils" in sys.modules and not isinstance(sys.modules["frappe.utils"], MagicMock):
    utils_mock = sys.modules["frappe.utils"]
else:
    import types
    utils_mock = types.ModuleType("frappe.utils")
    utils_mock.__path__ = []
    sys.modules["frappe.utils"] = utils_mock

if "frappe.model" in sys.modules and not isinstance(sys.modules["frappe.model"], MagicMock):
    model_mock = sys.modules["frappe.model"]
else:
    import types
    model_mock = types.ModuleType("frappe.model")
    model_mock.__path__ = []
    sys.modules["frappe.model"] = model_mock

if "frappe.model.document" in sys.modules and not isinstance(sys.modules["frappe.model.document"], MagicMock):
    doc_mock = sys.modules["frappe.model.document"]
else:
    import types
    doc_mock = types.ModuleType("frappe.model.document")
    doc_mock.__path__ = []
    sys.modules["frappe.model.document"] = doc_mock

def dummy_throw(msg, *args, **kwargs):
    raise ValueError(msg)

mock_frappe.throw = dummy_throw
utils_mock.now_datetime = lambda: datetime(2026, 7, 6, 10, 0, 0)
mock_frappe.utils = utils_mock

import frappe
from tap_buddy.tasks.scheduler import _dispatch_flow_campaign


class DummyCampaign:
    def __init__(self, name, glific_flow, flow_custom_parameters=None):
        self.name = name
        self.glific_flow = glific_flow
        self.flow_custom_parameters = flow_custom_parameters


class DummyRecipient:
    def __init__(self, name, school=None, whatsapp_group=None):
        self.name = name
        self.school = school
        self.whatsapp_group = whatsapp_group


class DummySchool:
    def __init__(self, name, whatsapp_number):
        self.name = name
        self.whatsapp_number = whatsapp_number


class DummyGroup:
    def __init__(self, name, glific_group_id):
        self.name = name
        self.glific_group_id = glific_group_id


class TestFlowDispatchOverrideMerging(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock()
        self.campaign = DummyCampaign("CAMP-FLOW-001", "flow_123")
        self.recipient = DummyRecipient("REC-001", school="Test School")
        self.school = DummySchool("Test School", "919876543210")
        self.orig_throw = frappe.throw
        frappe.throw = dummy_throw

    def tearDown(self):
        frappe.throw = self.orig_throw

    @patch("tap_buddy.tasks.scheduler.frappe")
    @patch("tap_buddy.tasks.scheduler.normalize_phone_number")
    @patch("tap_buddy.tasks.scheduler.get_recipient_context")
    @patch("tap_buddy.tasks.scheduler._create_dispatch_attempt")
    @patch("tap_buddy.tasks.scheduler._update_dispatch_attempt_success")
    @patch("tap_buddy.tasks.scheduler._mark_failed")
    def test_dispatch_flow_campaign_merges_custom_parameters(
        self,
        mock_mark_failed,
        mock_success,
        mock_attempt,
        mock_get_context,
        mock_normalize,
        mock_frappe_mod,
    ):
        """Verify custom parameters merge into default_results and override existing keys."""
        mock_frappe_mod.get_doc.return_value = self.school
        mock_frappe_mod.throw = dummy_throw
        mock_normalize.return_value = "919876543210"
        mock_get_context.return_value = {
            "school_name": "Test School Name",
            "district": "Old District",
            "state": "MH",
        }
        mock_attempt.return_value = "ATTEMPT-001"

        self.campaign.flow_custom_parameters = (
            '{"meeting_link": "https://zoom.us/test", "district": "Override District"}'
        )

        _dispatch_flow_campaign(self.mock_client, self.campaign, self.recipient)

        self.mock_client.start_contact_flow.assert_called_once()
        call_kwargs = self.mock_client.start_contact_flow.call_args[1]
        self.assertEqual(
            call_kwargs.get("default_results"),
            {
                "school_name": "Test School Name",
                "district": "Override District",
                "state": "MH",
                "meeting_link": "https://zoom.us/test",
            },
        )
        mock_mark_failed.assert_not_called()
        mock_success.assert_called_once()

    @patch("tap_buddy.tasks.scheduler.frappe")
    @patch("tap_buddy.tasks.scheduler.normalize_phone_number")
    @patch("tap_buddy.tasks.scheduler.get_recipient_context")
    @patch("tap_buddy.tasks.scheduler._create_dispatch_attempt")
    @patch("tap_buddy.tasks.scheduler._update_dispatch_attempt_success")
    @patch("tap_buddy.tasks.scheduler._mark_failed")
    def test_dispatch_flow_campaign_no_custom_parameters(
        self,
        mock_mark_failed,
        mock_success,
        mock_attempt,
        mock_get_context,
        mock_normalize,
        mock_frappe_mod,
    ):
        """Verify dispatch works normally without custom parameters."""
        mock_frappe_mod.get_doc.return_value = self.school
        mock_frappe_mod.throw = dummy_throw
        mock_normalize.return_value = "919876543210"
        mock_get_context.return_value = {
            "school_name": "Test School Name",
            "district": "Old District",
        }
        mock_attempt.return_value = "ATTEMPT-001"

        self.campaign.flow_custom_parameters = None

        _dispatch_flow_campaign(self.mock_client, self.campaign, self.recipient)

        self.mock_client.start_contact_flow.assert_called_once_with(
            "919876543210", "flow_123", default_results={"school_name": "Test School Name", "district": "Old District"}
        )
        mock_mark_failed.assert_not_called()
        mock_success.assert_called_once()

    @patch("tap_buddy.tasks.scheduler.frappe")
    @patch("tap_buddy.tasks.scheduler.normalize_phone_number")
    @patch("tap_buddy.tasks.scheduler.get_recipient_context")
    @patch("tap_buddy.tasks.scheduler._mark_failed")
    def test_dispatch_flow_campaign_invalid_json_does_not_crash(
        self,
        mock_mark_failed,
        mock_get_context,
        mock_normalize,
        mock_frappe_mod,
    ):
        """Verify malformed JSON logs an error and marks recipient failed without crashing loop."""
        mock_frappe_mod.get_doc.return_value = self.school
        mock_frappe_mod.throw = dummy_throw
        mock_normalize.return_value = "919876543210"

        self.campaign.flow_custom_parameters = '{"invalid_json": '

        # Should not raise exception
        _dispatch_flow_campaign(self.mock_client, self.campaign, self.recipient)

        self.mock_client.start_contact_flow.assert_not_called()
        mock_mark_failed.assert_called_once()
        self.assertTrue(mock_mark_failed.call_args[1].get("terminal") or mock_mark_failed.call_args[0][2] is False)

    @patch("tap_buddy.tasks.scheduler.frappe")
    @patch("tap_buddy.tasks.scheduler.normalize_phone_number")
    @patch("tap_buddy.tasks.scheduler.get_recipient_context")
    @patch("tap_buddy.tasks.scheduler._mark_failed")
    def test_dispatch_flow_campaign_array_json_fails(
        self,
        mock_mark_failed,
        mock_get_context,
        mock_normalize,
        mock_frappe_mod,
    ):
        """Verify non-dict JSON (like array) is rejected during dispatch without crashing loop."""
        mock_frappe_mod.get_doc.return_value = self.school
        mock_frappe_mod.throw = dummy_throw
        mock_normalize.return_value = "919876543210"

        self.campaign.flow_custom_parameters = '["not", "a", "dict"]'

        _dispatch_flow_campaign(self.mock_client, self.campaign, self.recipient)

        self.mock_client.start_contact_flow.assert_not_called()
        mock_mark_failed.assert_called_once()

    @patch("tap_buddy.tasks.scheduler.frappe")
    @patch("tap_buddy.tasks.scheduler.normalize_phone_number")
    @patch("tap_buddy.tasks.scheduler.get_recipient_context")
    @patch("tap_buddy.tasks.scheduler._create_dispatch_attempt")
    @patch("tap_buddy.tasks.scheduler._update_dispatch_attempt_success")
    @patch("tap_buddy.tasks.scheduler._mark_failed")
    def test_dispatch_flow_campaign_unknown_keys_and_nested_objects(
        self,
        mock_mark_failed,
        mock_success,
        mock_attempt,
        mock_get_context,
        mock_normalize,
        mock_frappe_mod,
    ):
        """Verify unknown parameter keys and nested JSON objects are cleanly preserved in default_results."""
        mock_frappe_mod.get_doc.return_value = self.school
        mock_frappe_mod.throw = dummy_throw
        mock_normalize.return_value = "919876543210"
        mock_get_context.return_value = {"school_name": "Test School"}
        mock_attempt.return_value = "ATTEMPT-001"

        self.campaign.flow_custom_parameters = (
            '{"unknown_param": "foo", "nested_meta": {"tier": 1, "region": "north"}}'
        )

        _dispatch_flow_campaign(self.mock_client, self.campaign, self.recipient)

        self.mock_client.start_contact_flow.assert_called_once_with(
            "919876543210",
            "flow_123",
            default_results={
                "school_name": "Test School",
                "unknown_param": "foo",
                "nested_meta": {"tier": 1, "region": "north"},
            },
        )
        mock_mark_failed.assert_not_called()
        mock_success.assert_called_once()

    @patch("tap_buddy.tasks.scheduler.frappe")
    @patch("tap_buddy.tasks.scheduler.normalize_phone_number")
    @patch("tap_buddy.tasks.scheduler.get_recipient_context")
    @patch("tap_buddy.tasks.scheduler._create_dispatch_attempt")
    @patch("tap_buddy.tasks.scheduler._update_dispatch_attempt_success")
    @patch("tap_buddy.tasks.scheduler._mark_failed")
    def test_dispatch_flow_campaign_null_and_empty_strings(
        self,
        mock_mark_failed,
        mock_success,
        mock_attempt,
        mock_get_context,
        mock_normalize,
        mock_frappe_mod,
    ):
        """Verify null values and empty strings override existing recipient context keys."""
        mock_frappe_mod.get_doc.return_value = self.school
        mock_frappe_mod.throw = dummy_throw
        mock_normalize.return_value = "919876543210"
        mock_get_context.return_value = {
            "school_name": "Test School Name",
            "meeting_link": "https://old.link",
            "district": "Old District",
        }
        mock_attempt.return_value = "ATTEMPT-001"

        self.campaign.flow_custom_parameters = '{"meeting_link": null, "district": ""}'

        _dispatch_flow_campaign(self.mock_client, self.campaign, self.recipient)

        self.mock_client.start_contact_flow.assert_called_once_with(
            "919876543210",
            "flow_123",
            default_results={
                "school_name": "Test School Name",
                "meeting_link": None,
                "district": "",
            },
        )
        mock_mark_failed.assert_not_called()
        mock_success.assert_called_once()

    @patch("tap_buddy.tasks.scheduler.frappe")
    @patch("tap_buddy.tasks.scheduler._create_dispatch_attempt")
    @patch("tap_buddy.tasks.scheduler._update_dispatch_attempt_success")
    @patch("tap_buddy.tasks.scheduler._mark_failed")
    def test_dispatch_flow_campaign_wa_group_flow(
        self,
        mock_mark_failed,
        mock_success,
        mock_attempt,
        mock_frappe_mod,
    ):
        """Verify WA Group Flow dispatch calls start_wa_group_flow without default_results (Glific API limitation)."""
        group_recipient = DummyRecipient("REC-GRP-001", whatsapp_group="WAG-001")
        dummy_group = DummyGroup("WAG-001", "glific_group_999")
        mock_frappe_mod.get_doc.return_value = dummy_group
        mock_attempt.return_value = "ATTEMPT-001"

        self.campaign.flow_custom_parameters = '{"meeting_link": "https://zoom.us/group"}'

        _dispatch_flow_campaign(self.mock_client, self.campaign, group_recipient)

        self.mock_client.start_wa_group_flow.assert_called_once_with("glific_group_999", "flow_123")
        self.mock_client.start_contact_flow.assert_not_called()
        mock_mark_failed.assert_not_called()
        mock_success.assert_called_once()


if __name__ == "__main__":
    unittest.main()
