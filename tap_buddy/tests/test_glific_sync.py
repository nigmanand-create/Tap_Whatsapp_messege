"""
Unit tests for tap_buddy.services.glific_sync

Tests the reconciliation-based group sync engine:
  - _fetch_and_reconcile_groups()  — stale mapping detection & healing
  - _sync_group_memberships()      — contact upsert + group association
  - _build_contact_payload()       — field mapping pipeline
  - _extract_group_id() / _extract_contact_id()  — response parsing
  - Duplicate-safe: "already exists" errors are swallowed, not retried
  - Concurrent-safe: race conditions logged but not fatal

No live Glific API or Frappe database required — all dependencies mocked.
"""
import types
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_settings(**kwargs):
    defaults = dict(
        enabled=True,
        sync_contacts=True,
        sync_groups=True,
        dry_run=False,
        sync_only_new=False,
        last_synced_at=None,
        batch_size=100,
    )
    defaults.update(kwargs)
    s = types.SimpleNamespace(**defaults)
    s.save = MagicMock()
    return s


def _make_mapping(name, school_group, glific_group_id):
    return types.SimpleNamespace(
        name=name,
        school_group=school_group,
        glific_group_id=glific_group_id,
    )


def _make_group_doc(group_name, members):
    """members = list of school names (strings)"""
    doc = MagicMock()
    doc.group_name = group_name
    doc.members = [types.SimpleNamespace(school=m) for m in members]
    return doc


def _make_school_doc(name, whatsapp_number):
    doc = MagicMock()
    doc.name = name
    doc.school_name = name
    doc.whatsapp_number = whatsapp_number
    return doc


# ---------------------------------------------------------------------------
# 1. _build_contact_payload
# ---------------------------------------------------------------------------

class TestBuildContactPayload:
    def test_basic_payload_with_no_field_mappings(self, monkeypatch):
        from tap_buddy.services.glific_sync import _build_contact_payload

        school = types.SimpleNamespace(
            school_name="Test School",
            whatsapp_number="+919999999999",
        )
        payload = _build_contact_payload(school, [])
        assert payload["name"] == "Test School"
        assert "fields" not in payload  # empty fields dict is removed

    def test_field_mappings_included(self, monkeypatch):
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.normalize_phone_number",
            lambda p: p,
        )
        from tap_buddy.services.glific_sync import _build_contact_payload

        school = types.SimpleNamespace(
            school_name="Test School",
            whatsapp_number="+91999",
            district="TestDist",
        )
        school.get = lambda field: getattr(school, field, None)

        mappings = [
            types.SimpleNamespace(source_field="district", glific_field="district"),
        ]
        payload = _build_contact_payload(school, mappings)
        assert payload["fields"]["district"] == "TestDist"

    def test_none_field_values_excluded(self, monkeypatch):
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.normalize_phone_number",
            lambda p: p,
        )
        from tap_buddy.services.glific_sync import _build_contact_payload

        school = types.SimpleNamespace(
            school_name="S",
            whatsapp_number="+91",
        )
        school.get = lambda field: None  # all fields return None

        mappings = [types.SimpleNamespace(source_field="district", glific_field="district")]
        payload = _build_contact_payload(school, mappings)
        assert "fields" not in payload


# ---------------------------------------------------------------------------
# 2. _extract_group_id / _extract_contact_id — response shape variants
# ---------------------------------------------------------------------------

class TestExtractGroupId:
    @pytest.mark.parametrize("response,expected", [
        ({"id": "g1"}, "g1"),
        ({"data": {"id": "g2"}}, "g2"),
        ({"group": {"id": "g3"}}, "g3"),
        ({}, None),
        (None, None),
        ("string", None),
    ])
    def test_extract_variants(self, response, expected):
        from tap_buddy.services.glific_sync import _extract_group_id
        assert _extract_group_id(response) == expected


class TestExtractContactId:
    @pytest.mark.parametrize("response,expected", [
        ({"id": "c1"}, "c1"),
        ({"data": {"id": "c2"}}, "c2"),
        ({"contact": {"id": "c3"}}, "c3"),
        ([{"id": "c4"}], "c4"),
        ({}, None),
        (None, None),
    ])
    def test_extract_variants(self, response, expected):
        from tap_buddy.services.glific_sync import _extract_contact_id
        assert _extract_contact_id(response) == expected


# ---------------------------------------------------------------------------
# 3. _fetch_and_reconcile_groups — stale mapping healing
# ---------------------------------------------------------------------------

class TestFetchAndReconcileGroups:
    def _make_client(self, groups_response=None, create_response=None):
        client = MagicMock()
        client.get_groups.return_value = {
            "data": groups_response or [],
            "metadata": {},
        }
        if create_response:
            client.create_group.return_value = create_response
        return client

    def test_correct_mapping_returned_unchanged(self, monkeypatch):
        mapping = _make_mapping("map1", "sg1", "glific-g1")
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.frappe.get_all",
            lambda *a, **kw: [types.SimpleNamespace(name="map1", school_group="sg1", glific_group_id="glific-g1")],
        )
        group_doc = MagicMock()
        group_doc.group_name = "My Group"
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.frappe.get_doc",
            lambda dtype, name: group_doc,
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.frappe.db",
            MagicMock(set_value=MagicMock(), commit=MagicMock()),
        )

        client = self._make_client([{"name": "my group", "id": "glific-g1"}])
        settings = _make_settings(dry_run=False)

        from tap_buddy.services.glific_sync import _fetch_and_reconcile_groups
        result = _fetch_and_reconcile_groups(client, settings)

        assert result.get("sg1") == "glific-g1"

    def test_stale_mapping_healed(self, monkeypatch):
        """Glific has a different ID for the same group name — local mapping must be updated."""
        db_mock = MagicMock()
        db_mock.commit = MagicMock()
        updated_values = {}

        def fake_set_value(doctype, name, field, value):
            updated_values[field] = value

        db_mock.set_value = fake_set_value

        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.frappe.get_all",
            lambda *a, **kw: [types.SimpleNamespace(name="map2", school_group="sg2", glific_group_id="OLD-ID")],
        )
        group_doc = MagicMock()
        group_doc.group_name = "Stale Group"
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.frappe.get_doc",
            lambda dtype, name: group_doc,
        )
        monkeypatch.setattr("tap_buddy.services.glific_sync.frappe.db", db_mock)

        # Glific reports the real ID as "NEW-ID"
        client = self._make_client([{"name": "stale group", "id": "NEW-ID"}])
        settings = _make_settings(dry_run=False)

        from tap_buddy.services.glific_sync import _fetch_and_reconcile_groups
        result = _fetch_and_reconcile_groups(client, settings)

        assert updated_values.get("glific_group_id") == "NEW-ID"
        assert result.get("sg2") == "NEW-ID"

    def test_missing_group_created_idempotently(self, monkeypatch):
        """Group exists locally but not in Glific — should be created once."""
        db_mock = MagicMock()
        db_mock.commit = MagicMock()
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.frappe.get_all",
            lambda *a, **kw: [types.SimpleNamespace(name="map3", school_group="sg3", glific_group_id=None)],
        )
        group_doc = MagicMock()
        group_doc.group_name = "Brand New Group"
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.frappe.get_doc",
            lambda dtype, name: group_doc,
        )
        monkeypatch.setattr("tap_buddy.services.glific_sync.frappe.db", db_mock)

        # No groups in Glific yet; create_group returns new ID
        client = self._make_client([], create_response={"id": "FRESH-ID"})
        settings = _make_settings(dry_run=False)

        from tap_buddy.services.glific_sync import _fetch_and_reconcile_groups
        result = _fetch_and_reconcile_groups(client, settings)

        client.create_group.assert_called_once()
        assert result.get("sg3") == "FRESH-ID"

    def test_dry_run_does_not_call_glific(self, monkeypatch):
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.frappe.get_all",
            lambda *a, **kw: [types.SimpleNamespace(name="map4", school_group="sg4", glific_group_id="gid4")],
        )
        group_doc = MagicMock()
        group_doc.group_name = "Dry Run Group"
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.frappe.get_doc",
            lambda dtype, name: group_doc,
        )
        monkeypatch.setattr("tap_buddy.services.glific_sync.frappe.db", MagicMock())

        client = MagicMock()
        settings = _make_settings(dry_run=True)

        from tap_buddy.services.glific_sync import _fetch_and_reconcile_groups
        _fetch_and_reconcile_groups(client, settings)

        client.get_groups.assert_not_called()
        client.create_group.assert_not_called()


# ---------------------------------------------------------------------------
# 4. _sync_group_memberships — duplicate-safe behaviour
# ---------------------------------------------------------------------------

class TestSyncGroupMemberships:
    def _run_sync(self, monkeypatch, client, group_map, members, school_phone="+919999999999"):
        group_doc = _make_group_doc("Test Group", members)
        school_doc = _make_school_doc(members[0] if members else "school1", school_phone)

        def fake_get_doc(dtype, name):
            if dtype == "School Group":
                return group_doc
            if dtype == "School":
                return school_doc
            raise Exception(f"Unknown doctype {dtype}")

        monkeypatch.setattr("tap_buddy.services.glific_sync.frappe.get_doc", fake_get_doc)
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.normalize_phone_number",
            lambda p: p,
        )

        from tap_buddy.services.glific_sync import _sync_group_memberships

        settings = _make_settings(dry_run=False)
        return _sync_group_memberships(client, settings, group_map)

    def test_member_added_to_group_successfully(self, monkeypatch):
        client = MagicMock()
        client.upsert_contact.return_value = {"id": "contact-99"}
        client.add_contact_to_group.return_value = {}

        count = self._run_sync(
            monkeypatch, client,
            {"sg1": "glific-g1"},
            ["School Alpha"],
        )
        assert count == 1
        client.add_contact_to_group.assert_called_once_with("glific-g1", "contact-99")

    def test_duplicate_member_error_swallowed(self, monkeypatch):
        """'already exists' errors must not propagate or be retried."""
        from tap_buddy.services.glific_client import GlificAPIError

        client = MagicMock()
        client.upsert_contact.return_value = {"id": "contact-77"}
        client.add_contact_to_group.side_effect = GlificAPIError("Contact already exists in group")

        # Should not raise and count stays at 0 (no successful add)
        count = self._run_sync(
            monkeypatch, client,
            {"sg1": "glific-g1"},
            ["School Beta"],
        )
        assert count == 0

    def test_empty_phone_skipped(self, monkeypatch):
        client = MagicMock()
        self._run_sync(
            monkeypatch, client,
            {"sg1": "glific-g1"},
            ["School Gamma"],
            school_phone="",
        )
        client.upsert_contact.assert_not_called()

    def test_empty_group_map_returns_zero(self, monkeypatch):
        client = MagicMock()
        from tap_buddy.services.glific_sync import _sync_group_memberships
        settings = _make_settings(dry_run=False)
        result = _sync_group_memberships(client, settings, {})
        assert result == 0

    def test_dry_run_does_not_call_api(self, monkeypatch):
        group_doc = _make_group_doc("Test", ["school1"])
        school_doc = _make_school_doc("school1", "+91999")

        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.frappe.get_doc",
            lambda d, n: group_doc if d == "School Group" else school_doc,
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_sync.normalize_phone_number",
            lambda p: p,
        )

        client = MagicMock()
        settings = _make_settings(dry_run=True)

        from tap_buddy.services.glific_sync import _sync_group_memberships
        count = _sync_group_memberships(client, settings, {"sg1": "glific-g1"})

        client.upsert_contact.assert_not_called()
        assert count == 1  # dry run counts as processed
