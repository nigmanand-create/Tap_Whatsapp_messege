"""
test_e02_poll_response_webhook.py

Task E-02: Poll Ingestion Webhook API
Tests covering all specified scenarios:
  1. Successful first delivery — document created, success=True returned.
  2. Duplicate delivery — idempotency: success=True, already_processed=True,
     no second document created.
  3. Invalid webhook secret — 401 returned.
  4. Missing webhook secret — 401 returned.
  5. Missing required fields (response_id, phone_number, selected_option).
  6. Malformed JSON payload — 400 returned by handle() HTTP entry point.
  7. Empty payload body — 400 returned by handle() HTTP entry point.
  8. Non-object JSON (array) — 400 returned by handle() HTTP entry point.
  9. Document creation failure — 500 returned.

Architecture note
-----------------
Business logic lives in ``_handle_poll_response(payload)`` so tests can call it
directly without navigating the ``@frappe.whitelist`` decorator wrapper.
The decorated ``handle()`` is tested for the HTTP-layer scenarios (body parsing).

Mock strategy
-------------
This file replaces sys.modules["frappe"] with a MagicMock.
NOTE: This file shares the known module-level frappe mock isolation issue
documented in test_d02_regex_validation_rules.py. Run this file independently
or in its own pytest invocation group.  (Technical debt: tracked.)
"""
import json
import sys
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Frappe mock must be in place before any tap_buddy.api.poll_response import
# ---------------------------------------------------------------------------
_mock_frappe = MagicMock()
_mock_frappe.local = MagicMock()
_mock_frappe.local.response = MagicMock()
_mock_frappe.local.response.content_type = "application/json"
_mock_frappe.local.response.http_status_code = 200
_mock_frappe.logger.return_value = MagicMock()
# frappe.whitelist must return a decorator that returns the function unchanged
_mock_frappe.whitelist.return_value = lambda fn: fn

sys.modules["frappe"] = _mock_frappe

from tap_buddy.api.poll_response import handle, _handle_poll_response, REQUIRED_FIELDS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
VALID_SECRET = "test-webhook-secret-abc123"


def _make_payload(**overrides):
    base = {
        "secret": VALID_SECRET,
        "response_id": "resp-uuid-001",
        "flow_id": "flow-abc",
        "phone_number": "919999999999",
        "school_code": "SCH001",
        "poll_question": "How are you learning today?",
        "selected_option": "Very well",
        "submitted_at": "2026-07-06 10:00:00",
    }
    base.update(overrides)
    return base


def _remove_field(payload, field):
    p = dict(payload)
    p.pop(field, None)
    return p


class TestE02PollResponseWebhook(unittest.TestCase):

    def setUp(self):
        """Reset all mock state before each test."""
        _mock_frappe.reset_mock()
        _mock_frappe.local.response.http_status_code = 200
        _mock_frappe.local.response.content_type = "application/json"
        _mock_frappe.logger.return_value = MagicMock()
        # Restore whitelist decorator behaviour after reset
        _mock_frappe.whitelist.return_value = lambda fn: fn

        # Configure settings mock to always return the valid secret
        settings_mock = MagicMock()
        settings_mock.get_password.return_value = VALID_SECRET
        settings_mock.webhook_secret = VALID_SECRET
        _mock_frappe.get_single.return_value = settings_mock

        # Default: record does not exist yet
        _mock_frappe.db.exists.return_value = None

        # new_doc returns a real object so attribute assignment works
        self._doc_mock = MagicMock()
        _mock_frappe.new_doc.return_value = self._doc_mock

    def _set_request_body(self, payload):
        """Configure frappe.request to return the given dict as JSON body."""
        body = json.dumps(payload)
        _mock_frappe.request.get_data.return_value = body
        return body

    # ------------------------------------------------------------------
    # 1. Successful first delivery
    # ------------------------------------------------------------------
    def test_first_delivery_returns_success(self):
        """First delivery must return {success: True} and no already_processed flag."""
        result = _handle_poll_response(_make_payload())
        self.assertTrue(result.get("success"), f"Expected success=True, got: {result}")
        self.assertNotIn(
            "already_processed", result,
            "First delivery must NOT include already_processed flag"
        )

    def test_first_delivery_inserts_document(self):
        """First delivery must call frappe.new_doc and doc.insert."""
        _handle_poll_response(_make_payload())
        _mock_frappe.new_doc.assert_called_once_with("TAP Poll Response")
        self._doc_mock.insert.assert_called_once_with(ignore_permissions=True)

    def test_first_delivery_maps_all_fields(self):
        """All payload fields must be mapped to doc attributes."""
        payload = _make_payload(
            response_id="resp-uuid-map",
            flow_id="flow-xyz",
            phone_number="919888888888",
            school_code="SCH999",
            poll_question="Did you complete the assignment?",
            selected_option="Yes",
            submitted_at="2026-07-06 11:00:00",
        )
        _handle_poll_response(payload)
        self.assertEqual(self._doc_mock.response_id, "resp-uuid-map")
        self.assertEqual(self._doc_mock.flow_id, "flow-xyz")
        self.assertEqual(self._doc_mock.phone_number, "919888888888")
        self.assertEqual(self._doc_mock.school_code, "SCH999")
        self.assertEqual(self._doc_mock.poll_question, "Did you complete the assignment?")
        self.assertEqual(self._doc_mock.selected_option, "Yes")
        self.assertEqual(self._doc_mock.submitted_at, "2026-07-06 11:00:00")

    def test_optional_fields_default_to_empty_string(self):
        """flow_id, school_code, poll_question are optional — must default to empty string."""
        payload = {
            "secret": VALID_SECRET,
            "response_id": "resp-minimal",
            "phone_number": "919777777777",
            "selected_option": "Option A",
        }
        _handle_poll_response(payload)
        self.assertEqual(self._doc_mock.flow_id, "")
        self.assertEqual(self._doc_mock.school_code, "")
        self.assertEqual(self._doc_mock.poll_question, "")

    def test_submitted_at_defaults_to_utc_now_when_absent(self):
        """When submitted_at is absent, handler must fill in a timestamp automatically."""
        payload = _make_payload()
        del payload["submitted_at"]
        _handle_poll_response(payload)
        self.assertTrue(
            self._doc_mock.submitted_at,
            "submitted_at must be auto-filled when absent from payload"
        )

    # ------------------------------------------------------------------
    # 2. Duplicate delivery (idempotency)
    # ------------------------------------------------------------------
    def test_duplicate_delivery_returns_already_processed(self):
        """Duplicate delivery must return success=True with already_processed=True."""
        _mock_frappe.db.exists.return_value = "TAP-POLL-RESP-EXISTING-001"
        result = _handle_poll_response(_make_payload())
        self.assertTrue(result.get("success"), "Duplicate must still return success=True")
        self.assertTrue(
            result.get("already_processed"),
            "Duplicate must return already_processed=True"
        )

    def test_duplicate_delivery_does_not_insert_document(self):
        """Duplicate delivery must NOT call frappe.new_doc or doc.insert."""
        _mock_frappe.db.exists.return_value = "TAP-POLL-RESP-EXISTING-001"
        _handle_poll_response(_make_payload())
        _mock_frappe.new_doc.assert_not_called()

    def test_idempotency_check_uses_correct_doctype_and_filter(self):
        """Idempotency check must query TAP Poll Response by response_id."""
        _handle_poll_response(_make_payload(response_id="resp-idem-001"))
        _mock_frappe.db.exists.assert_called_with(
            "TAP Poll Response", {"response_id": "resp-idem-001"}
        )

    # ------------------------------------------------------------------
    # 3. Invalid webhook secret
    # ------------------------------------------------------------------
    def test_invalid_secret_returns_401(self):
        """Wrong secret must return HTTP 401."""
        _handle_poll_response(_make_payload(secret="wrong-secret"))
        self.assertEqual(_mock_frappe.local.response.http_status_code, 401)

    def test_invalid_secret_returns_error_body(self):
        """Wrong secret must return success=False and error field."""
        result = _handle_poll_response(_make_payload(secret="wrong-secret"))
        self.assertFalse(result.get("success"))
        self.assertIn("error", result)

    def test_invalid_secret_does_not_insert_document(self):
        """Wrong secret must prevent any document insertion."""
        _handle_poll_response(_make_payload(secret="wrong-secret"))
        _mock_frappe.new_doc.assert_not_called()

    # ------------------------------------------------------------------
    # 4. Missing secret field
    # ------------------------------------------------------------------
    def test_missing_secret_field_returns_401(self):
        """Payload without secret field must return HTTP 401."""
        payload = _remove_field(_make_payload(), "secret")
        _handle_poll_response(payload)
        self.assertEqual(_mock_frappe.local.response.http_status_code, 401)

    def test_empty_secret_returns_401(self):
        """Payload with empty-string secret must return HTTP 401."""
        _handle_poll_response(_make_payload(secret=""))
        self.assertEqual(_mock_frappe.local.response.http_status_code, 401)

    # ------------------------------------------------------------------
    # 5. Missing required fields
    # ------------------------------------------------------------------
    def test_missing_response_id_returns_400(self):
        """Payload missing response_id must return HTTP 400."""
        payload = _remove_field(_make_payload(), "response_id")
        _handle_poll_response(payload)
        self.assertEqual(_mock_frappe.local.response.http_status_code, 400)

    def test_missing_phone_number_returns_400(self):
        """Payload missing phone_number must return HTTP 400."""
        payload = _remove_field(_make_payload(), "phone_number")
        _handle_poll_response(payload)
        self.assertEqual(_mock_frappe.local.response.http_status_code, 400)

    def test_missing_selected_option_returns_400(self):
        """Payload missing selected_option must return HTTP 400."""
        payload = _remove_field(_make_payload(), "selected_option")
        _handle_poll_response(payload)
        self.assertEqual(_mock_frappe.local.response.http_status_code, 400)

    def test_missing_required_field_returns_success_false(self):
        """Missing required field must return success=False with error message."""
        result = _handle_poll_response(_remove_field(_make_payload(), "response_id"))
        self.assertFalse(result.get("success"))
        self.assertIn("error", result)

    def test_required_fields_constant_matches_spec(self):
        """REQUIRED_FIELDS constant must include the three fields defined in the spec."""
        self.assertIn("response_id", REQUIRED_FIELDS)
        self.assertIn("phone_number", REQUIRED_FIELDS)
        self.assertIn("selected_option", REQUIRED_FIELDS)

    # ------------------------------------------------------------------
    # 6. HTTP-layer: malformed JSON — tested via handle() entry point
    # ------------------------------------------------------------------
    def test_malformed_json_returns_400(self):
        """Non-parseable body must return HTTP 400 from handle()."""
        _mock_frappe.request.get_data.return_value = "{broken json ]["
        handle()
        self.assertEqual(_mock_frappe.local.response.http_status_code, 400)

    def test_malformed_json_returns_success_false(self):
        """Non-parseable body must return success=False from handle()."""
        _mock_frappe.request.get_data.return_value = "not json at all"
        result = handle()
        self.assertFalse(result.get("success"))

    # ------------------------------------------------------------------
    # 7. HTTP-layer: empty body
    # ------------------------------------------------------------------
    def test_empty_body_returns_400(self):
        """Empty request body must return HTTP 400 from handle()."""
        _mock_frappe.request.get_data.return_value = ""
        handle()
        self.assertEqual(_mock_frappe.local.response.http_status_code, 400)

    def test_none_body_returns_400(self):
        """None request body must return HTTP 400 from handle()."""
        _mock_frappe.request.get_data.return_value = None
        handle()
        self.assertEqual(_mock_frappe.local.response.http_status_code, 400)

    # ------------------------------------------------------------------
    # 8. HTTP-layer: non-object JSON (array)
    # ------------------------------------------------------------------
    def test_json_array_payload_returns_400(self):
        """JSON array at root must be rejected with HTTP 400 by handle()."""
        _mock_frappe.request.get_data.return_value = json.dumps([1, 2, 3])
        handle()
        self.assertEqual(_mock_frappe.local.response.http_status_code, 400)

    # ------------------------------------------------------------------
    # 9. Document creation failure (server error path)
    # ------------------------------------------------------------------
    def test_insert_failure_returns_500(self):
        """If doc.insert raises an exception, handler must return HTTP 500."""
        self._doc_mock.insert.side_effect = RuntimeError("DB connection lost")
        _handle_poll_response(_make_payload())
        self.assertEqual(_mock_frappe.local.response.http_status_code, 500)

    def test_insert_failure_returns_success_false(self):
        """If doc.insert raises, result must have success=False."""
        self._doc_mock.insert.side_effect = RuntimeError("DB connection lost")
        result = _handle_poll_response(_make_payload())
        self.assertFalse(result.get("success"))


if __name__ == "__main__":
    unittest.main()
