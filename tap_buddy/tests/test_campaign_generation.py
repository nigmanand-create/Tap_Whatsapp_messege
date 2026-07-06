# -*- coding: utf-8 -*-
"""
Comprehensive Unit Tests for Campaign Generation Service (Phase 3)
==================================================================
Covers successful generation, transaction rollback, duplicate prevention,
naming patterns, history creation, linkage, failure recovery, and analytics isolation.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import sys

# Set up clean mocks for frappe environment
try:
    import frappe
    import frappe.utils
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

def dummy_get_datetime(val):
    if isinstance(val, datetime):
        return val
    return datetime.strptime(str(val), "%Y-%m-%d %H:%M:%S")

utils_mock.get_datetime = dummy_get_datetime
utils_mock.now_datetime = lambda: datetime(2026, 7, 3, 10, 0, 0)
mock_frappe.utils = utils_mock

for attr in ("db", "get_doc", "new_doc", "throw", "logger", "get_all"):
    if not hasattr(mock_frappe, attr) or not isinstance(getattr(mock_frappe, attr), MagicMock):
        setattr(mock_frappe, attr, MagicMock())

from tap_buddy.services.campaign_generation import CampaignGenerationService


class DummyTemplateDoc:
    def __init__(self, name="Template-001", **kwargs):
        self.name = name
        self.template_name = kwargs.get("template_name", "Weekly Update")
        self.naming_pattern = kwargs.get("naming_pattern", "{template_name} - {YYYY}-{MM}-{DD}")
        self.campaign_type = kwargs.get("campaign_type", "Template")
        self.template = kwargs.get("template", "wa_template_id")
        self.glific_flow = kwargs.get("glific_flow", None)
        self.targeting_type = kwargs.get("targeting_type", "Single School")
        self.school_name = kwargs.get("school_name", "SCH-001")
        self.school_group = kwargs.get("school_group", None)
        self.target_collection = kwargs.get("target_collection", None)
        self.variable_mappings = kwargs.get("variable_mappings", [])
        self.flow_custom_parameters = kwargs.get("flow_custom_parameters", None)


class DummyNewDoc:
    def __init__(self, doctype):
        self.doctype = doctype
        self.name = f"{doctype}-GEN-001"
        self._appended = {}

    def append(self, fieldname, row):
        if fieldname not in self._appended:
            self._appended[fieldname] = []
        self._appended[fieldname].append(row)

    def insert(self, ignore_permissions=False):
        return self


class DummyCampaignDoc:
    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "CMP-2026-00001")
        self.naming_pattern = kwargs.get("naming_pattern")
        self.campaign_name = kwargs.get("campaign_name")
        self.campaign_type = kwargs.get("campaign_type")
        self.template = kwargs.get("template")
        self.glific_flow = kwargs.get("glific_flow")
        self.targeting_type = kwargs.get("targeting_type")
        self.school_name = kwargs.get("school_name")
        self.school_group = kwargs.get("school_group")
        self.target_collection = kwargs.get("target_collection")
        self.status = kwargs.get("status", "Draft")
        self.scheduled_time = kwargs.get("scheduled_time")
        self.flow_custom_parameters = kwargs.get("flow_custom_parameters", None)
        self.recurring_campaign_template = kwargs.get("recurring_campaign_template")
        self.__dict__.update(kwargs)

    def insert(self, ignore_permissions=False):
        return self


class TestCampaignGenerationService(unittest.TestCase):
    def setUp(self):
        if hasattr(mock_frappe, "reset_mock"):
            mock_frappe.reset_mock()
        else:
            for attr in ("db", "get_doc", "new_doc", "throw", "logger", "get_all"):
                if hasattr(mock_frappe, attr) and hasattr(getattr(mock_frappe, attr), "reset_mock"):
                    getattr(mock_frappe, attr).reset_mock()
        mock_frappe.utils = utils_mock
        for attr in ("db", "get_doc", "new_doc", "throw", "logger", "get_all"):
            if not hasattr(mock_frappe, attr) or not isinstance(getattr(mock_frappe, attr), MagicMock):
                setattr(mock_frappe, attr, MagicMock())
        mock_frappe.db.exists.side_effect = None
        mock_frappe.db.exists.return_value = False
        mock_frappe.new_doc.side_effect = None
        mock_frappe.db.rollback = MagicMock()
        mock_frappe.db.savepoint = MagicMock()

    def tearDown(self):
        mock_frappe.db.exists.side_effect = None
        mock_frappe.new_doc.side_effect = None

    def test_naming_patterns_exact(self):
        # 1. Weekly Registration Reminder - Week 28
        doc1 = DummyTemplateDoc(
            template_name="Weekly Registration Reminder",
            naming_pattern="{template_name} - Week {W}"
        )
        # 2026-07-13 is Monday of ISO/python week 28
        dt1 = datetime(2026, 7, 13, 9, 0, 0)
        name1 = CampaignGenerationService.format_campaign_name(doc1, dt1)
        self.assertEqual(name1, "Weekly Registration Reminder - Week 28")

        # 2. Monthly Engagement Report - July 2026
        doc2 = DummyTemplateDoc(
            template_name="Monthly Engagement Report",
            naming_pattern="{template_name} - {Month} {YYYY}"
        )
        dt2 = datetime(2026, 7, 1, 9, 0, 0)
        name2 = CampaignGenerationService.format_campaign_name(doc2, dt2)
        self.assertEqual(name2, "Monthly Engagement Report - July 2026")

        # 3. Daily Attendance Reminder - 2026-07-03
        doc3 = DummyTemplateDoc(
            template_name="Daily Attendance Reminder",
            naming_pattern="{template_name} - {YYYY}-{MM}-{DD}"
        )
        dt3 = datetime(2026, 7, 3, 9, 0, 0)
        name3 = CampaignGenerationService.format_campaign_name(doc3, dt3)
        self.assertEqual(name3, "Daily Attendance Reminder - 2026-07-03")

    def test_successful_generation_and_linkage(self):
        created_docs = []
        def mock_new_doc(dt):
            doc = DummyNewDoc(dt)
            created_docs.append(doc)
            return doc
            
        mock_frappe.new_doc.side_effect = mock_new_doc
        mock_frappe.db.exists.return_value = False

        template = DummyTemplateDoc("RCT-001", template_name="Daily Reminder")
        scheduled_dt = datetime(2026, 7, 3, 9, 0, 0)

        c_name = CampaignGenerationService.generate_campaign(template, scheduled_dt)
        
        # Verify savepoint was created
        mock_frappe.db.savepoint.assert_called_once_with("generate_campaign_sp")

        # Verify exactly 2 documents created: TAP Campaign and Generated Campaign History
        self.assertEqual(len(created_docs), 2)
        camp_doc = created_docs[0]
        hist_doc = created_docs[1]

        self.assertEqual(camp_doc.doctype, "TAP Campaign")
        self.assertEqual(camp_doc.campaign_name, "Daily Reminder - 2026-07-03")
        self.assertEqual(camp_doc.status, "Scheduled")
        self.assertEqual(camp_doc.send_date, "2026-07-03 09:00:00")
        self.assertEqual(camp_doc.targeting_type, "Single School")
        self.assertEqual(camp_doc.school_name, "SCH-001")

        # Verify analytics isolation (Requirement 3)
        self.assertEqual(camp_doc.total_recipients, 0)
        self.assertEqual(camp_doc.sent_count, 0)
        self.assertEqual(camp_doc.delivered_count, 0)
        self.assertEqual(camp_doc.failed_count, 0)

        # Verify history linkage (Requirement 4)
        self.assertEqual(hist_doc.doctype, "Generated Campaign History")
        self.assertEqual(hist_doc.parent, "RCT-001")
        self.assertEqual(hist_doc.parenttype, "Recurring Campaign Template")
        self.assertEqual(hist_doc.parentfield, "generated_campaigns")
        self.assertEqual(hist_doc.campaign, camp_doc.name)
        self.assertEqual(hist_doc.status, "Generated")

    def test_transaction_rollback(self):
        def mock_new_doc(dt):
            doc = DummyNewDoc(dt)
            if dt == "Generated Campaign History":
                raise RuntimeError("DB Connection Lost during child table insert")
            return doc

        mock_frappe.new_doc.side_effect = mock_new_doc
        mock_frappe.db.exists.return_value = False

        template = DummyTemplateDoc("RCT-FAIL")
        with self.assertRaises(RuntimeError):
            CampaignGenerationService.generate_campaign(template, "2026-07-03 09:00:00")

        # Verify rollback was called immediately upon insert failure
        mock_frappe.db.rollback.assert_called_once()

    def test_duplicate_prevention(self):
        # Simulate idempotency key already exists in Generated Campaign History
        mock_frappe.db.exists.return_value = True
        mock_frappe.db.get_value.return_value = "EXISTING-CAMP-001"

        template = DummyTemplateDoc("RCT-DUP")
        c_name = CampaignGenerationService.generate_campaign(template, "2026-07-03 09:00:00")

        # Should return existing campaign and not create any new docs
        self.assertEqual(c_name, "EXISTING-CAMP-001")
        mock_frappe.new_doc.assert_not_called()

    def test_failure_recovery_in_plan_generation(self):
        plan = {
            "template_name": "T-PLAN",
            "planned_windows": ["2026-07-03 09:00:00", "2026-07-04 09:00:00"],
            "status": "PENDING"
        }
        template = DummyTemplateDoc("T-PLAN")

        # First window succeeds, second window throws error
        call_count = [0]
        def mock_gen(t, win, idempotency_key=None):
            call_count[0] += 1
            if call_count[0] == 2:
                raise ValueError("Simulated creation failure on second window")
            return "CAMP-001"

        with patch.object(CampaignGenerationService, "generate_campaign", side_effect=mock_gen):
            with self.assertRaises(ValueError):
                CampaignGenerationService.generate_from_plan(template, plan)

        # Verify plan status marked failed so scheduler won't advance next_execution_date
        self.assertEqual(plan["status"], "FAILED")
        self.assertIn("Simulated creation failure", plan["error"])

    def test_duplicate_insert_db_unique_constraint(self):
        class MockDuplicateError(Exception):
            pass
        if not hasattr(mock_frappe, "exceptions"):
            mock_frappe.exceptions = MagicMock()
        mock_frappe.exceptions.DuplicateEntryError = MockDuplicateError

        def mock_new_doc(dt):
            doc = DummyNewDoc(dt)
            if dt == "Generated Campaign History":
                raise MockDuplicateError("Duplicate entry 'RCT:T-DUP:202607030900' for key 'idempotency_key'")
            return doc

        mock_frappe.new_doc.side_effect = mock_new_doc
        mock_frappe.db.exists.return_value = False
        mock_frappe.db.get_value.return_value = "EXISTING-CAMP-DUP"

        template = DummyTemplateDoc("T-DUP")
        c_name = CampaignGenerationService.generate_campaign(template, "2026-07-03 09:00:00")

        # Verify rollback executed to clear failed insert attempt
        mock_frappe.db.rollback.assert_called()
        # Verify returned existing campaign cleanly without failing
        self.assertEqual(c_name, "EXISTING-CAMP-DUP")

    def test_generate_campaign_copies_flow_custom_parameters(self):
        created_docs = []
        def mock_new_doc(dt):
            doc = DummyNewDoc(dt)
            created_docs.append(doc)
            return doc

        mock_frappe.new_doc.side_effect = mock_new_doc
        mock_frappe.db.exists.return_value = False

        custom_params = '{"meeting_link": "https://zoom.us/test", "week_number": "Week 10"}'
        template = DummyTemplateDoc(
            name="T-FLOW-001",
            campaign_type="Flow",
            glific_flow="flow_123",
            flow_custom_parameters=custom_params
        )
        c_name = CampaignGenerationService.generate_campaign(template, "2026-07-03 09:00:00")

        self.assertEqual(c_name, "TAP Campaign-GEN-001")
        campaign_doc = [doc for doc in created_docs if doc.doctype == "TAP Campaign"][0]
        self.assertEqual(getattr(campaign_doc, "flow_custom_parameters", None), custom_params)


if __name__ == "__main__":
    unittest.main()
