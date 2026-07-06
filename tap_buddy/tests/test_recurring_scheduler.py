# -*- coding: utf-8 -*-
"""
Comprehensive Unit Tests for Recurring Campaign Scheduler & Execution Engine
============================================================================
Covers daily, weekly, monthly, cron schedules, timezone conversion,
idempotency, missed execution policies, distributed locking, and concurrency.
"""

import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime
import sys
import pytz

# Set up dummy get_datetime and now_datetime helpers
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

from tap_buddy.tasks.recurring import (
    calculate_next_execution,
    preview_next_executions,
    compute_idempotency_key,
    apply_missed_execution_policy,
    create_execution_plan,
    evaluate_recurring_templates,
    GLOBAL_LOCK_KEY
)

class MockCache:
    def __init__(self):
        self.store = {}

    def set_value(self, key, val, expires_in_sec=None, nx=False):
        if nx and key in self.store:
            return False
        self.store[key] = val
        return True

    def get_value(self, key):
        return self.store.get(key)

    def delete_value(self, key):
        if key in self.store:
            del self.store[key]

class DummyTemplateDoc:
    def __init__(self, name, **kwargs):
        self.name = name
        self.recurrence_type = kwargs.get("recurrence_type", "Daily")
        self.execution_timezone = kwargs.get("execution_timezone", "Asia/Kolkata")
        self.cron_expression = kwargs.get("cron_expression")
        self.missed_execution_policy = kwargs.get("missed_execution_policy", "Skip missed executions")
        self.start_date = kwargs.get("start_date", "2026-07-01 09:00:00")
        self.next_execution_date = kwargs.get("next_execution_date", "2026-07-01 09:00:00")
        self.end_date = kwargs.get("end_date")

class TestRecurringScheduler(unittest.TestCase):
    def setUp(self):
        self.cache = MockCache()
        mock_frappe.cache = lambda: self.cache
        mock_frappe.db.exists.side_effect = None
        mock_frappe.db.exists.return_value = False
        mock_frappe.get_all.side_effect = None
        mock_frappe.get_doc.side_effect = None
        mock_frappe.db.set_value.side_effect = None

    def tearDown(self):
        mock_frappe.db.exists.side_effect = None
        mock_frappe.get_all.side_effect = None
        mock_frappe.get_doc.side_effect = None
        mock_frappe.db.set_value.side_effect = None

    def test_calculate_next_execution_daily(self):
        from_dt = datetime(2026, 7, 1, 3, 30, 0) # 9:00 AM IST in UTC
        next_dt = calculate_next_execution("Daily", from_dt, "Asia/Kolkata")
        self.assertEqual(next_dt, datetime(2026, 7, 2, 3, 30, 0))

    def test_calculate_next_execution_weekly(self):
        # 2026-07-01 is Wednesday
        from_dt = datetime(2026, 7, 1, 3, 30, 0)
        next_dt = calculate_next_execution("Weekly", from_dt, "Asia/Kolkata")
        self.assertEqual(next_dt, datetime(2026, 7, 8, 3, 30, 0))

    def test_calculate_next_execution_monthly(self):
        from_dt = datetime(2026, 7, 1, 3, 30, 0)
        next_dt = calculate_next_execution("Monthly", from_dt, "Asia/Kolkata")
        self.assertEqual(next_dt, datetime(2026, 8, 1, 3, 30, 0))

    def test_calculate_next_execution_cron(self):
        from_dt = datetime(2026, 7, 1, 3, 30, 0) # 09:00 IST
        # Run every 6 hours: 0 */6 * * *
        next_dt = calculate_next_execution("Custom Cron", from_dt, "Asia/Kolkata", cron_expression="0 */6 * * *")
        # Next 6-hour interval after 09:00 IST is 12:00 IST (06:30 UTC)
        self.assertEqual(next_dt, datetime(2026, 7, 1, 6, 30, 0))

    def test_timezone_conversion(self):
        # Start at 09:00 UTC
        from_dt = datetime(2026, 7, 1, 9, 0, 0)
        next_utc = calculate_next_execution("Daily", from_dt, "UTC")
        self.assertEqual(next_utc, datetime(2026, 7, 2, 9, 0, 0))

    def test_preview_next_executions(self):
        doc = DummyTemplateDoc("Template A", recurrence_type="Daily", start_date="2026-07-01 03:30:00")
        previews = preview_next_executions(doc, count=5, from_dt=datetime(2026, 7, 1, 3, 30, 0))
        self.assertEqual(len(previews), 5)
        self.assertEqual(previews[0], "2026-07-02 03:30:00")
        self.assertEqual(previews[4], "2026-07-06 03:30:00")

    def test_idempotency_key_generation(self):
        dt = datetime(2026, 7, 2, 9, 15, 0)
        key = compute_idempotency_key("Weekly Reminder", dt)
        self.assertEqual(key, "RCT:Weekly Reminder:202607020915")

    def test_missed_execution_policies(self):
        w1 = datetime(2026, 7, 1, 9, 0, 0)
        w2 = datetime(2026, 7, 2, 9, 0, 0)
        w3 = datetime(2026, 7, 3, 9, 0, 0)
        windows = [w1, w2, w3]

        # 1. Skip missed executions
        planned, skipped = apply_missed_execution_policy(windows, "Skip missed executions")
        self.assertEqual(planned, [])
        self.assertEqual(skipped, windows)

        # 2. Catch up latest only
        planned, skipped = apply_missed_execution_policy(windows, "Catch up latest only")
        self.assertEqual(planned, [w3])
        self.assertEqual(skipped, [w1, w2])

        # 3. Catch up all
        planned, skipped = apply_missed_execution_policy(windows, "Catch up all")
        self.assertEqual(planned, windows)
        self.assertEqual(skipped, [])

    def test_idempotency_skip_executed_windows(self):
        doc = DummyTemplateDoc(
            "Idempotent Template",
            recurrence_type="Daily",
            next_execution_date="2026-07-01 09:00:00",
            missed_execution_policy="Catch up all"
        )
        # Suppose 2026-07-01 09:00:00 was already executed
        def mock_exists(doctype, filters):
            return "202607010900" in filters.get("idempotency_key", "")
        
        mock_frappe.db.exists.side_effect = mock_exists

        plan = create_execution_plan(doc, current_dt=datetime(2026, 7, 3, 10, 0, 0))
        # 07-01 should be excluded from due/planned because it exists in DB
        self.assertNotIn("2026-07-01 09:00:00", plan["planned_windows"])
        self.assertIn("2026-07-02 09:00:00", plan["planned_windows"])
        self.assertIn("2026-07-03 09:00:00", plan["planned_windows"])

    def test_distributed_lock_global_collision(self):
        # Lock global key first
        self.cache.set_value(GLOBAL_LOCK_KEY, "locked")
        res = evaluate_recurring_templates(current_dt=datetime(2026, 7, 3, 10, 0, 0))
        self.assertEqual(res["status"], "SKIPPED_LOCKED")
        self.assertEqual(res["scanned"], 0)

    def test_distributed_lock_template_collision(self):
        class Row:
            def __init__(self, n):
                self.name = n

        # Two active templates: T1 and T2
        mock_frappe.get_all.return_value = [Row("T1"), Row("T2")]
        # Simulate T1 locked by worker A
        self.cache.set_value("tap_buddy:recurring_template_lock:T1", "locked")

        docs = {
            "T1": DummyTemplateDoc("T1"),
            "T2": DummyTemplateDoc("T2")
        }
        mock_frappe.get_doc.side_effect = lambda dt, name: docs[name]

        res = evaluate_recurring_templates(current_dt=datetime(2026, 7, 3, 10, 0, 0))
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["scanned"], 2)
        # Only T2 should have a generated plan because T1 was locked
        self.assertEqual(len(res["plans"]), 1)
        self.assertEqual(res["plans"][0]["template_name"], "T2")

    def test_duplicate_scheduler_execution(self):
        class Row:
            def __init__(self, n):
                self.name = n

        t1 = DummyTemplateDoc("T1", next_execution_date="2026-07-01 09:00:00")
        docs = {"T1": t1}
        
        # When get_all runs, return T1 only if next_execution_date <= now
        def mock_get_all(doctype, filters, fields):
            now = datetime(2026, 7, 3, 10, 0, 0)
            target = dummy_get_datetime(t1.next_execution_date)
            return [Row("T1")] if target <= now else []

        mock_frappe.get_all.side_effect = mock_get_all
        mock_frappe.get_doc.side_effect = lambda dt, name: docs[name]

        def mock_set_value(doctype, name, field, val):
            setattr(docs[name], field, val)
        mock_frappe.db.set_value.side_effect = mock_set_value

        # First run at 2026-07-03 10:00:00
        res1 = evaluate_recurring_templates(current_dt=datetime(2026, 7, 3, 10, 0, 0))
        self.assertEqual(len(res1["plans"]), 1)
        # After first run, next_execution_date should have advanced past 2026-07-03 10:00:00
        self.assertGreater(dummy_get_datetime(t1.next_execution_date), datetime(2026, 7, 3, 10, 0, 0))

        # Second run immediately after
        res2 = evaluate_recurring_templates(current_dt=datetime(2026, 7, 3, 10, 0, 0))
        self.assertEqual(res2["scanned"], 0)
        self.assertEqual(len(res2["plans"]), 0)

    @patch("tap_buddy.services.campaign_generation.CampaignGenerationService.generate_from_plan")
    def test_failed_generation_leaves_next_execution_date_unchanged_for_retry(self, mock_gen):
        class Row:
            def __init__(self, n):
                self.name = n

        t1 = DummyTemplateDoc("T1", next_execution_date="2026-07-01 09:00:00")
        docs = {"T1": t1}

        mock_frappe.get_all.return_value = [Row("T1")]
        mock_frappe.get_doc.side_effect = lambda dt, name: docs[name]

        def mock_set_value(doctype, name, field, val):
            setattr(docs[name], field, val)
        mock_frappe.db.set_value.side_effect = mock_set_value
        mock_frappe.db.rollback = MagicMock()

        # Simulate creation failure on run 1
        mock_gen.side_effect = RuntimeError("Simulated Glific/DB failure")

        res1 = evaluate_recurring_templates(current_dt=datetime(2026, 7, 3, 10, 0, 0))
        # Verify rollback was called and next_execution_date remained unchanged
        mock_frappe.db.rollback.assert_called()
        self.assertEqual(t1.next_execution_date, "2026-07-01 09:00:00")

        # Now simulate success on run 2 (scheduler retry)
        mock_gen.side_effect = None
        mock_gen.return_value = ["T1 - 2026-07-03"]

        res2 = evaluate_recurring_templates(current_dt=datetime(2026, 7, 3, 10, 0, 0))
        # Verify next_execution_date now advanced
        self.assertNotEqual(t1.next_execution_date, "2026-07-01 09:00:00")

if __name__ == "__main__":
    unittest.main()
