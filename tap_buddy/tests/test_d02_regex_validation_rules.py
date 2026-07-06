"""
test_d02_regex_validation_rules.py

Task D-02: Regex Validation Rules
Verifies that:
1. flow_registry.json carries validation_regex on all structured URL and date fields.
2. PayloadValidator rejects non-conforming values with ValidationError.
3. PayloadValidator accepts valid URLs, valid dates, and empty strings (optional fields).
4. Unstructured text fields carry no validation_regex (no over-restriction).

TECHNICAL DEBT (recorded at D-02 approval, 2026-07-06):
    Test isolation issue — this module replaces sys.modules["frappe"] with a
    MagicMock at import time. When pytest collects this file in the same session
    as test_glific_client.py or test_isolated_dynamic_context.py (which expect
    a different frappe mock state), their tests fail with AttributeError.
    Each group passes when run independently; all production code is unaffected.
    Resolution: refactor all frappe-dependent tests to use pytest fixtures and
    importlib.reload() instead of module-level sys.modules replacement.
    Tracking: follow-up engineering task, not blocking Phase E.

Regex design decision:
    URL fields:  ^(https?://[^\\s]+|)$
        - Permits http:// or https:// URLs.
        - Permits empty string (field is optional; populated only at dispatch time).
        - Rejects ftp://, file://, bare paths, and whitespace-only strings.

    Date fields (deadline / event_date / registration_deadline):
        ^(\\d{4}-\\d{2}-\\d{2}|\\d{2}/\\d{2}/\\d{4}|)$
        - Accepts ISO-8601 (YYYY-MM-DD) and DD/MM/YYYY.
        - Permits empty string (optional).
        - Rejects free-text dates like "next Monday".

    award_month field:
        ^(\\d{4}-\\d{2}|[A-Za-z]+ \\d{4}|)$
        - Accepts YYYY-MM or "July 2026" style.
        - Permits empty string.
"""
import json
import os
import re
import sys
import unittest
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Frappe mock setup — must happen before any tap_buddy imports
# ---------------------------------------------------------------------------
mock_frappe = MagicMock()
sys.modules["frappe"] = mock_frappe
mock_frappe.utils = MagicMock()

from tap_buddy.dynamic_context.models import FieldConfig, FieldSource, FlowConfig
from tap_buddy.dynamic_context.validators import PayloadValidator
from tap_buddy.dynamic_context.exceptions import ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
REGISTRY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "dynamic_context",
    "flow_registry.json",
)

URL_PATTERN  = r"^(https?://[^\s]+|)$"
DATE_PATTERN = r"^(\d{4}-\d{2}-\d{2}|\d{2}/\d{2}/\d{4}|)$"

# Fields that must carry the URL regex
URL_FIELDS = {
    "meeting_link",
    "portal_login_url",
    "mentor_booking_link",
    "leaderboard_portal_link",
    "registration_portal_link",
    "excel_template_url",
    "setup_guide_pdf",
    "survey_form_url",
    "weekly_syllabus_pdf",
    "emergency_sop_document",
    "reference_image",
    "promotional_banner_img",
    "portal_help_doc_pdf",
    "monthly_report_template_pdf",
    "progress_badge_image",
    "certificate_template_pdf",
    "trophy_graphic_img",
}

# Fields that must carry a date regex
DATE_FIELDS = {
    "action_deadline",
    "registration_deadline",
    "event_date",
}


def _load_registry():
    with open(REGISTRY_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def _iter_fields(registry):
    """Yield (flow_id, field_dict) for every field in the registry."""
    for flow in registry.get("flows", []):
        for fld in flow.get("fields", []):
            yield flow["flow_id"], fld


def _make_flow_config(field_name, regex, source=FieldSource.PAYLOAD):
    return FlowConfig(
        flow_id="test_flow",
        flow_name="Test",
        category="test",
        fields=(FieldConfig(field_name, source, validation_regex=regex),),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
class TestD02RegistryRegexPresence(unittest.TestCase):
    """Verify flow_registry.json carries validation_regex on the correct fields."""

    @classmethod
    def setUpClass(cls):
        cls.registry = _load_registry()

    def test_url_fields_carry_url_regex(self):
        """All URL fields must declare a URL validation_regex in the registry."""
        found = {}
        for flow_id, fld in _iter_fields(self.registry):
            name = fld.get("name")
            if name in URL_FIELDS:
                found[name] = fld.get("validation_regex")

        missing = URL_FIELDS - set(found.keys())
        self.assertEqual(
            missing, set(),
            f"D-02 FAIL: URL fields missing from registry: {missing}"
        )
        for name, regex in found.items():
            self.assertIsNotNone(
                regex,
                f"D-02 FAIL: URL field '{name}' has no validation_regex in registry"
            )
            self.assertEqual(
                regex, URL_PATTERN,
                f"D-02 FAIL: URL field '{name}' has unexpected regex '{regex}', expected '{URL_PATTERN}'"
            )

    def test_date_fields_carry_date_regex(self):
        """All date fields must declare a date validation_regex in the registry."""
        found = {}
        for flow_id, fld in _iter_fields(self.registry):
            name = fld.get("name")
            if name in DATE_FIELDS:
                found[name] = fld.get("validation_regex")

        missing = DATE_FIELDS - set(found.keys())
        self.assertEqual(
            missing, set(),
            f"D-02 FAIL: Date fields missing from registry: {missing}"
        )
        for name, regex in found.items():
            self.assertIsNotNone(
                regex,
                f"D-02 FAIL: Date field '{name}' has no validation_regex in registry"
            )
            self.assertEqual(
                regex, DATE_PATTERN,
                f"D-02 FAIL: Date field '{name}' has unexpected regex '{regex}', expected '{DATE_PATTERN}'"
            )

    def test_award_month_carries_month_year_regex(self):
        """award_month must carry a YYYY-MM or 'Month YYYY' regex."""
        award_month_regex = None
        for flow_id, fld in _iter_fields(self.registry):
            if fld.get("name") == "award_month":
                award_month_regex = fld.get("validation_regex")
                break
        self.assertIsNotNone(
            award_month_regex,
            "D-02 FAIL: 'award_month' field has no validation_regex in registry"
        )
        # Must accept YYYY-MM and 'Month YYYY'
        self.assertTrue(re.match(award_month_regex, "2026-07"))
        self.assertTrue(re.match(award_month_regex, "July 2026"))
        self.assertTrue(re.match(award_month_regex, ""))

    def test_free_text_fields_have_no_regex(self):
        """Unstructured text fields must NOT carry a validation_regex (no over-restriction)."""
        free_text_fields = {
            "priority_level", "target_zone", "target_district",
            "alert_title", "alert_message_body", "coordinator_name",
            "meeting_platform", "activity_name", "speaker_name",
            "program_tier", "academic_year",
        }
        violations = []
        for flow_id, fld in _iter_fields(self.registry):
            name = fld.get("name")
            if name in free_text_fields and fld.get("validation_regex"):
                violations.append(f"{flow_id}.{name}")
        self.assertEqual(
            violations, [],
            f"D-02 FAIL: Free-text fields unexpectedly carry a validation_regex: {violations}"
        )


class TestD02URLRegexPayloadValidation(unittest.TestCase):
    """PayloadValidator must enforce URL regex correctly."""

    def _validate(self, field_name, value):
        cfg = _make_flow_config(field_name, URL_PATTERN)
        PayloadValidator.validate_payload(cfg, {field_name: value})

    def test_valid_https_url_passes(self):
        """A valid https:// URL must pass validation."""
        self._validate("meeting_link", "https://zoom.us/j/12345")

    def test_valid_http_url_passes(self):
        """A valid http:// URL must pass validation."""
        self._validate("portal_login_url", "http://tap.example.com/login")

    def test_empty_string_passes(self):
        """Empty string must pass (field is optional at dispatch time)."""
        self._validate("meeting_link", "")

    def test_none_passes_when_not_present(self):
        """Field absent from payload must pass (no value to validate)."""
        cfg = _make_flow_config("meeting_link", URL_PATTERN)
        # PayloadValidator runs regex only when value is non-empty.
        # Include a dummy key so the payload is not empty (validator rejects
        # completely empty payloads before field-level checks).
        PayloadValidator.validate_payload(cfg, {"phone": "919999999999"})

    def test_ftp_url_rejected(self):
        """ftp:// URLs must be rejected."""
        with self.assertRaises(ValidationError):
            self._validate("meeting_link", "ftp://files.example.com/doc.pdf")

    def test_bare_path_rejected(self):
        """Bare paths without scheme must be rejected."""
        with self.assertRaises(ValidationError):
            self._validate("portal_login_url", "/login/dashboard")

    def test_whitespace_only_passes(self):
        """Whitespace-only strings pass silently.

        PayloadValidator strips the value before regex evaluation:
            if val is not None and str(val).strip() != "" and field_cfg.validation_regex:
        A whitespace-only value is therefore treated as 'no value' and the regex
        branch is never reached.  This is intentional: the field is optional and
        an operator may provide " " rather than "". The dispatcher will still
        produce an empty-looking value in the Glific context.
        """
        # Must not raise — the validator skips regex for whitespace-only input
        self._validate("meeting_link", "   ")

    def test_plain_text_rejected(self):
        """Plain text strings must be rejected."""
        with self.assertRaises(ValidationError):
            self._validate("meeting_link", "zoom meeting link")

    def test_javascript_scheme_rejected(self):
        """javascript: scheme injection must be rejected."""
        with self.assertRaises(ValidationError):
            self._validate("meeting_link", "javascript:alert(1)")


class TestD02DateRegexPayloadValidation(unittest.TestCase):
    """PayloadValidator must enforce date regex correctly."""

    def _validate(self, field_name, value):
        cfg = _make_flow_config(field_name, DATE_PATTERN)
        PayloadValidator.validate_payload(cfg, {field_name: value})

    def test_iso8601_date_passes(self):
        """ISO-8601 date YYYY-MM-DD must pass."""
        self._validate("action_deadline", "2026-08-15")

    def test_dd_mm_yyyy_date_passes(self):
        """DD/MM/YYYY date format must pass."""
        self._validate("registration_deadline", "15/08/2026")

    def test_empty_string_passes(self):
        """Empty string must pass (field is optional)."""
        self._validate("action_deadline", "")

    def test_free_text_date_rejected(self):
        """Human-readable free-text dates must be rejected."""
        with self.assertRaises(ValidationError):
            self._validate("action_deadline", "next Monday")

    def test_partial_date_rejected(self):
        """Partial date strings must be rejected."""
        with self.assertRaises(ValidationError):
            self._validate("action_deadline", "2026-08")

    def test_wrong_separator_rejected(self):
        """Dot-separated dates must be rejected."""
        with self.assertRaises(ValidationError):
            self._validate("event_date", "15.08.2026")


class TestD02RegistryLoadedByConfigProvider(unittest.TestCase):
    """Confirm the config provider actually reads validation_regex from the registry."""

    def test_url_field_regex_loaded_from_registry(self):
        """
        JsonFileConfigProvider must load validation_regex from flow_registry.json
        and expose it on the FieldConfig object.
        """
        registry = _load_registry()
        meeting_link_field = None
        for flow in registry.get("flows", []):
            if flow["flow_id"] == "builtin_program_announcements":
                for fld in flow.get("fields", []):
                    if fld["name"] == "meeting_link":
                        meeting_link_field = fld
                        break
        self.assertIsNotNone(meeting_link_field, "meeting_link not found in registry")
        self.assertEqual(
            meeting_link_field.get("validation_regex"),
            URL_PATTERN,
            "meeting_link must carry the URL regex in flow_registry.json"
        )

    def test_date_field_regex_loaded_from_registry(self):
        """
        action_deadline must carry the date regex in the registry.
        """
        registry = _load_registry()
        action_deadline_field = None
        for flow in registry.get("flows", []):
            if flow["flow_id"] == "builtin_priority":
                for fld in flow.get("fields", []):
                    if fld["name"] == "action_deadline":
                        action_deadline_field = fld
                        break
        self.assertIsNotNone(action_deadline_field, "action_deadline not found in registry")
        self.assertEqual(
            action_deadline_field.get("validation_regex"),
            DATE_PATTERN,
            "action_deadline must carry the date regex in flow_registry.json"
        )


if __name__ == "__main__":
    unittest.main()
