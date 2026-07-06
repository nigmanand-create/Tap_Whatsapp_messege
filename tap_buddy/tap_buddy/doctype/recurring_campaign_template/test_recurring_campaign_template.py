# -*- coding: utf-8 -*-
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import sys

# Mock frappe module and submodules before importing controller
mock_frappe = MagicMock()
class MockValidationError(Exception):
    pass
mock_frappe.exceptions.ValidationError = MockValidationError
mock_frappe.throw.side_effect = MockValidationError

sys.modules["frappe"] = mock_frappe
sys.modules["frappe.model"] = MagicMock()
sys.modules["frappe.model.document"] = MagicMock()
sys.modules["frappe.utils"] = MagicMock()

# Define dummy Document class so inheritance works cleanly
class DummyDocument:
    def __init__(self, *args, **kwargs):
        pass

sys.modules["frappe.model.document"].Document = DummyDocument

from tap_buddy.tap_buddy.doctype.recurring_campaign_template.recurring_campaign_template import RecurringCampaignTemplate

class TestRecurringCampaignTemplate(unittest.TestCase):
    def setUp(self):
        mock_frappe.reset_mock()
        mock_frappe.throw.side_effect = MockValidationError

    def test_naming_formatting(self):
        doc = RecurringCampaignTemplate()
        doc.template_name = "Weekly Update"
        doc.naming_pattern = "{template_name} - Week {WW} ({YYYY}-{MM}-{DD})"
        dt = datetime(2026, 7, 2, 10, 0, 0)
        formatted = doc.format_campaign_name(dt)
        self.assertIn("Weekly Update", formatted)
        self.assertIn("2026-07-02", formatted)

    def test_validation_date_order(self):
        doc = RecurringCampaignTemplate()
        doc.template_name = "Invalid Date Template"
        doc.recurrence_type = "Daily"
        doc.start_date = "2026-07-10 09:00:00"
        doc.end_date = "2026-07-01 09:00:00"
        doc.campaign_type = "Flow"
        doc.glific_flow = "dummy_flow"
        doc.targeting_type = "Single School"
        doc.school_name = "dummy_school"

        with patch("tap_buddy.tap_buddy.doctype.recurring_campaign_template.recurring_campaign_template.get_datetime", lambda x: datetime.strptime(str(x), "%Y-%m-%d %H:%M:%S")):
            with self.assertRaises(MockValidationError):
                doc.validate()

    def test_validation_success(self):
        doc = RecurringCampaignTemplate()
        doc.template_name = "Valid Template"
        doc.recurrence_type = "Daily"
        doc.start_date = "2026-07-01 09:00:00"
        doc.end_date = "2026-07-10 09:00:00"
        doc.campaign_type = "Flow"
        doc.glific_flow = "dummy_flow"
        doc.targeting_type = "Single School"
        doc.school_name = "dummy_school"

        with patch("tap_buddy.tap_buddy.doctype.recurring_campaign_template.recurring_campaign_template.get_datetime", lambda x: datetime.strptime(str(x), "%Y-%m-%d %H:%M:%S")):
            doc.validate() # Should not raise exception
