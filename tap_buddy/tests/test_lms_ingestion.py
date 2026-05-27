import types
import datetime
from unittest.mock import MagicMock, patch

from tap_buddy.services.lms_ingestion import poll_lms_students

# ---------------------------------------------------------------------------
# TEST FIXTURE SECURITY NOTICE
# ---------------------------------------------------------------------------
# All credentials in this file are safe, non-functional mock placeholders.
# Do NOT replace them with real API keys, tokens, or secrets.
# ---------------------------------------------------------------------------

_MOCK_LMS_BASE_URL = "https://lms.example-test.invalid"
_MOCK_LMS_API_KEY = "mock-api-user:mock-api-secret-00000"
_FIXED_NOW = datetime.datetime(2026, 5, 26, 10, 0, 0)


def _make_settings():
    s = types.SimpleNamespace()
    s.polling_enabled = True
    s.lms_base_url = _MOCK_LMS_BASE_URL
    s.lms_api_key = _MOCK_LMS_API_KEY
    s.last_polled_at = None
    s.save = lambda ignore_permissions=True: None
    return s


def test_poll_lms_students_enqueues(monkeypatch):
    # Provide fake settings via frappe.get_single
    monkeypatch.setattr("frappe.get_single", lambda name: _make_settings())

    # Fake LMSClient to return two student records
    records = [{"name": "S1", "phone": "+91111"}, {"name": "S2", "phone": "+92222"}]

    class FakeClient:
        def get_students(self, fields=None, limit_page_length=20, filters=None):
            return {"data": records}

    monkeypatch.setattr("tap_buddy.services.lms_ingestion.LMSClient", lambda: FakeClient())

    enqueued = []

    def fake_enqueue(payload, raw_body=None, signature=None, source=None):
        enqueued.append(payload)
        return ["ok"]

    monkeypatch.setattr("tap_buddy.services.lms_ingestion.enqueue_lms_events", fake_enqueue)

    # Patch frappe.utils.now_datetime (used inside poll_lms_students) to avoid
    # requiring a live Frappe/database context in this unit test.
    monkeypatch.setattr(
        "tap_buddy.services.lms_ingestion.now_datetime",
        lambda: _FIXED_NOW,
    )

    # Patch frappe.log_error used in the exception handler
    monkeypatch.setattr("frappe.log_error", lambda **kw: None)
    monkeypatch.setattr("frappe.get_traceback", lambda: "")

    res = poll_lms_students(limit=20)

    assert res.get("status") == "ok"
    assert res.get("processed") == 2
    assert len(enqueued) == 2
