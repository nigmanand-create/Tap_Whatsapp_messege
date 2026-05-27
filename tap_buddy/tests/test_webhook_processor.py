"""
Unit tests for tap_buddy.services.webhook_processor

Tests the Redis-buffered webhook pipeline introduced in the architectural upgrade:
  - buffer_webhook_payload()  — O(1) ingestion into Redis
  - process_webhook_batches() — batch drain, dedup, hierarchy resolution, DLQ routing

These tests run WITHOUT a live Redis or Frappe database. All external calls
are monkeypatched.
"""
import json
from unittest.mock import MagicMock, call, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

def _make_item(provider_message_id: str, status: str) -> dict:
    """Build a wrapped webhook item as stored in the Redis queue."""
    return {
        "payload": {
            "provider_message_id": provider_message_id,
            "status": status,
        },
        "signature": "sha256=abc",
        "received_at": "2026-05-26T10:00:00",
    }


def _make_items(*pairs) -> list:
    """pairs = [(msg_id, status), ...]"""
    return [_make_item(mid, st) for mid, st in pairs]


# ---------------------------------------------------------------------------
# 1. buffer_webhook_payload — ingestion path
# ---------------------------------------------------------------------------

class TestBufferWebhookPayload:
    """Verify that buffer_webhook_payload pushes every item to Redis."""

    def test_single_dict_pushed_as_one_item(self, monkeypatch):
        pushed = []
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor.push_to_queue",
            lambda queue, item: pushed.append((queue, item)),
        )
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor.now_datetime",
            lambda: MagicMock(isoformat=lambda: "2026-05-26T10:00:00"),
        )

        from tap_buddy.services.webhook_processor import buffer_webhook_payload

        count = buffer_webhook_payload({"provider_message_id": "m1", "status": "sent"})

        assert count == 1
        assert len(pushed) == 1
        assert pushed[0][0] == "webhooks"
        assert pushed[0][1]["payload"]["provider_message_id"] == "m1"

    def test_list_payload_pushes_each_item(self, monkeypatch):
        pushed = []
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor.push_to_queue",
            lambda queue, item: pushed.append(item),
        )
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor.now_datetime",
            lambda: MagicMock(isoformat=lambda: "t"),
        )

        from tap_buddy.services.webhook_processor import buffer_webhook_payload

        payloads = [
            {"provider_message_id": "m1", "status": "sent"},
            {"provider_message_id": "m2", "status": "delivered"},
        ]
        count = buffer_webhook_payload(payloads)

        assert count == 2
        assert len(pushed) == 2

    def test_empty_queue_returns_zero(self, monkeypatch):
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor.pop_from_queue_batch",
            lambda *a, **kw: [],
        )

        from tap_buddy.services.webhook_processor import process_webhook_batches

        result = process_webhook_batches()
        assert result == 0


# ---------------------------------------------------------------------------
# 2. process_webhook_batches — deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    """Verify in-memory deduplication and status-hierarchy resolution."""

    def _run_batch(self, monkeypatch, items: list) -> dict:
        """Run process_webhook_batches with a fixed item list; return deduped map passed to _bulk_update_status."""
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor.pop_from_queue_batch",
            lambda *a, **kw: items,
        )
        captured = {}

        def fake_bulk_update(deduped_map):
            captured.update(deduped_map)

        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor._bulk_update_status",
            fake_bulk_update,
        )
        monkeypatch.setattr("tap_buddy.services.webhook_processor.frappe", MagicMock())

        from tap_buddy.services.webhook_processor import process_webhook_batches

        process_webhook_batches()
        return captured

    def test_duplicate_same_status_kept_once(self, monkeypatch):
        items = _make_items(("m1", "sent"), ("m1", "sent"))
        result = self._run_batch(monkeypatch, items)
        assert "m1" in result
        assert result["m1"]["status"] == "Sent"

    def test_higher_status_wins(self, monkeypatch):
        # delivered > sent in hierarchy
        items = _make_items(("m1", "sent"), ("m1", "delivered"))
        result = self._run_batch(monkeypatch, items)
        assert result["m1"]["status"] == "Delivered"

    def test_lower_status_does_not_overwrite_higher(self, monkeypatch):
        # read arrives first, then sent — read should be preserved
        items = _make_items(("m1", "read"), ("m1", "sent"))
        result = self._run_batch(monkeypatch, items)
        assert result["m1"]["status"] == "Read"

    def test_multiple_messages_kept_distinct(self, monkeypatch):
        items = _make_items(("m1", "sent"), ("m2", "delivered"), ("m3", "read"))
        result = self._run_batch(monkeypatch, items)
        assert len(result) == 3
        assert result["m1"]["status"] == "Sent"
        assert result["m2"]["status"] == "Delivered"
        assert result["m3"]["status"] == "Read"

    def test_flood_all_same_message_id_resolved_to_highest(self, monkeypatch):
        """Simulates a replay storm: 1000 events for the same message, random order."""
        statuses = ["sent", "delivered", "sent", "read", "delivered", "sent"] * 166 + ["read"]
        items = [_make_item("storm-msg", s) for s in statuses]
        result = self._run_batch(monkeypatch, items)
        assert result["storm-msg"]["status"] == "Read"


# ---------------------------------------------------------------------------
# 3. Dead-letter queue routing
# ---------------------------------------------------------------------------

class TestDLQRouting:
    """Items with missing provider_message_id or status go to the DLQ."""

    def _run_dlq_batch(self, monkeypatch, items):
        dlq = []
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor.pop_from_queue_batch",
            lambda *a, **kw: items,
        )
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor._bulk_update_status",
            lambda m: None,
        )
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor._route_to_dlq",
            lambda item, reason: dlq.append((item, reason)),
        )
        monkeypatch.setattr("tap_buddy.services.webhook_processor.frappe", MagicMock())

        from tap_buddy.services.webhook_processor import process_webhook_batches

        process_webhook_batches()
        return dlq

    def test_missing_provider_message_id_routes_to_dlq(self, monkeypatch):
        items = [{"payload": {"status": "sent"}, "signature": None, "received_at": "t"}]
        dlq = self._run_dlq_batch(monkeypatch, items)
        assert len(dlq) == 1
        assert "Missing" in dlq[0][1]

    def test_missing_status_routes_to_dlq(self, monkeypatch):
        items = [{"payload": {"provider_message_id": "m1"}, "signature": None, "received_at": "t"}]
        dlq = self._run_dlq_batch(monkeypatch, items)
        assert len(dlq) == 1

    def test_unknown_status_routes_to_dlq(self, monkeypatch):
        items = [_make_item("m1", "completely_unknown_status")]
        dlq = self._run_dlq_batch(monkeypatch, items)
        assert len(dlq) == 1

    def test_valid_items_do_not_go_to_dlq(self, monkeypatch):
        items = _make_items(("m1", "sent"), ("m2", "delivered"))
        dlq = self._run_dlq_batch(monkeypatch, items)
        assert len(dlq) == 0

    def test_mixed_valid_and_poison_items(self, monkeypatch):
        items = [
            _make_item("m1", "sent"),
            {"payload": {}, "signature": None, "received_at": "t"},  # poison
            _make_item("m2", "delivered"),
        ]
        dlq = self._run_dlq_batch(monkeypatch, items)
        # Only the poison item should be DLQ'd
        assert len(dlq) == 1


# ---------------------------------------------------------------------------
# 4. Status normalization & extraction
# ---------------------------------------------------------------------------

class TestStatusNormalization:
    """Ensure all Glific status strings map correctly."""

    @pytest.mark.parametrize("raw,expected", [
        ("sent", "Sent"),
        ("SENT", "Sent"),
        ("Sent", "Sent"),
        ("delivered", "Delivered"),
        ("read", "Read"),
        ("failed", "Failed"),
        ("undelivered", "Failed"),
        ("error", "Failed"),
        ("unknown_xyz", None),
        ("", None),
    ])
    def test_normalize_status(self, raw, expected):
        from tap_buddy.services.webhook_processor import _normalize_status
        assert _normalize_status(raw) == expected


# ---------------------------------------------------------------------------
# 5. Provider message ID extraction — nested payload shapes
# ---------------------------------------------------------------------------

class TestProviderMessageIdExtraction:
    """Handles the various nested payload shapes Glific may send."""

    @pytest.mark.parametrize("payload,expected", [
        ({"provider_message_id": "abc"}, "abc"),
        ({"message_id": "def"}, "def"),
        ({"id": "ghi"}, "ghi"),
        ({"message": {"provider_message_id": "nested"}}, "nested"),
        ({"data": {"id": "data-nested"}}, "data-nested"),
        ({}, None),
        ("not-a-dict", None),
    ])
    def test_extract_provider_message_id(self, payload, expected):
        from tap_buddy.services.webhook_processor import _extract_provider_message_id
        assert _extract_provider_message_id(payload) == expected


# ---------------------------------------------------------------------------
# 6. Logging safety — no raw payloads in logs
# ---------------------------------------------------------------------------

class TestLoggingSafety:
    """Verify poison-message logging does NOT dump raw payload."""

    def test_poison_message_log_does_not_contain_phone_number(self, monkeypatch):
        """A payload containing a phone number should NOT appear in the log."""
        phone = "+919012345678"
        poison_item = {
            "payload": {"phone": phone, "invalid": True},
            "signature": None,
            "received_at": "t",
        }

        log_messages = []

        class FakeLogger:
            def error(self, msg):
                log_messages.append(msg)

        fake_frappe = MagicMock()
        fake_frappe.logger.return_value = FakeLogger()

        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor.pop_from_queue_batch",
            lambda *a, **kw: [poison_item],
        )
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor._bulk_update_status",
            lambda m: None,
        )
        monkeypatch.setattr(
            "tap_buddy.services.webhook_processor._route_to_dlq",
            lambda i, r: None,
        )
        monkeypatch.setattr("tap_buddy.services.webhook_processor.frappe", fake_frappe)

        from tap_buddy.services.webhook_processor import process_webhook_batches

        process_webhook_batches()

        for msg in log_messages:
            assert phone not in str(msg), (
                f"Phone number leaked into log message: {msg}"
            )
