import frappe
from frappe.utils import now_datetime

from tap_buddy.utils.constants import (
    QUEUE_SHORT,
    REC_STATUS_DELIVERED,
    REC_STATUS_FAILED,
    REC_STATUS_READ,
    REC_STATUS_SENT,
)


STATUS_MAP = {
    "sent": REC_STATUS_SENT,
    "delivered": REC_STATUS_DELIVERED,
    "read": REC_STATUS_READ,
    "failed": REC_STATUS_FAILED,
    "undelivered": REC_STATUS_FAILED,
    "error": REC_STATUS_FAILED,
}


def enqueue_webhook_events(payload, raw_body=None, signature=None):
    event_names = []
    items = payload if isinstance(payload, list) else [payload]

    for item in items:
        event_name = _create_event(item, raw_body, signature)
        if not event_name:
            continue
        event_names.append(event_name)
        frappe.enqueue(
            "tap_buddy.services.webhook_processor.process_webhook_event",
            queue=QUEUE_SHORT,
            job_name=f"tap_buddy_webhook_{event_name}",
            event_name=event_name,
        )

    return event_names


def process_pending_events(limit=100):
    pending = frappe.get_all(
        "Webhook Event",
        filters={"processed": 0},
        fields=["name"],
        limit=limit,
        order_by="creation asc",
    )

    for row in pending:
        process_webhook_event(row.name)


def process_webhook_event(event_name):
    event = frappe.get_doc("Webhook Event", event_name)
    if event.processed:
        return

    payload = _parse_payload(event.payload)
    provider_message_id = event.provider_message_id or _extract_provider_message_id(payload)
    status = event.status or _extract_status(payload)
    normalized = _normalize_status(status)

    if not provider_message_id or not normalized:
        _mark_event_error(event, "Missing provider_message_id or status")
        return

    message_log = _get_message_log(provider_message_id)
    if not message_log:
        _mark_event_error(event, "Message Log not found for provider_message_id")
        return

    _apply_status_to_message_log(message_log, normalized)
    _apply_status_to_recipient(message_log.campaign, message_log.school, normalized)

    event.provider_message_id = provider_message_id
    event.status = normalized
    event.processed = 1
    event.processed_at = now_datetime()
    event.save(ignore_permissions=True)


def _create_event(payload, raw_body=None, signature=None):
    status = _normalize_status(_extract_status(payload))
    provider_message_id = _extract_provider_message_id(payload)

    if provider_message_id and status:
        existing = frappe.get_all(
            "Webhook Event",
            filters={"provider_message_id": provider_message_id, "status": status},
            fields=["name"],
            limit=1,
        )
        if existing:
            return existing[0].name

    event = frappe.new_doc("Webhook Event")
    event.provider = "Glific"
    event.provider_message_id = provider_message_id
    event.status = status
    event.event_type = _extract_event_type(payload)
    event.payload = frappe.as_json(payload)
    event.signature = signature
    event.received_at = now_datetime()
    event.processed = 0
    event.insert(ignore_permissions=True)
    return event.name


def _parse_payload(payload_text):
    if not payload_text:
        return {}
    if isinstance(payload_text, dict):
        return payload_text
    return frappe.parse_json(payload_text)


def _extract_event_type(payload):
    for key in ("event", "type", "event_type"):
        value = _read_payload_value(payload, key)
        if value:
            return str(value)
    return None


def _extract_status(payload):
    for key in ("status", "message_status", "delivery_status", "state"):
        value = _read_payload_value(payload, key)
        if value:
            return str(value)
    event_type = _extract_event_type(payload)
    if event_type and "." in event_type:
        return event_type.split(".")[-1]
    return None


def _extract_provider_message_id(payload):
    for key in ("provider_message_id", "message_id", "messageId", "id"):
        value = _read_payload_value(payload, key)
        if value:
            return str(value)
    return None


def _read_payload_value(payload, key):
    if not isinstance(payload, dict):
        return None
    if key in payload:
        return payload.get(key)
    if "message" in payload and isinstance(payload["message"], dict):
        return payload["message"].get(key)
    if "data" in payload and isinstance(payload["data"], dict):
        return payload["data"].get(key)
    return None


def _normalize_status(status):
    if not status:
        return None
    normalized = str(status).strip().lower()
    return STATUS_MAP.get(normalized)


def _get_message_log(provider_message_id):
    rows = frappe.get_all(
        "Message Log",
        filters={"provider_message_id": provider_message_id},
        fields=["name", "status", "campaign", "school", "sent_at", "delivered_at", "read_at"],
        limit=1,
    )
    return rows[0] if rows else None


def _apply_status_to_message_log(message_log, status):
    if not _should_update_status(message_log.status, status):
        return

    updates = {"status": status}
    now = now_datetime()

    if status == REC_STATUS_SENT and not message_log.sent_at:
        updates["sent_at"] = now
    elif status == REC_STATUS_DELIVERED and not message_log.delivered_at:
        updates["delivered_at"] = now
    elif status == REC_STATUS_READ and not message_log.read_at:
        updates["read_at"] = now

    frappe.db.set_value("Message Log", message_log.name, updates)


def _apply_status_to_recipient(campaign, school, status):
    recipient = frappe.get_all(
        "Campaign Recipient",
        filters={"campaign": campaign, "school": school},
        fields=["name", "status"],
        limit=1,
    )
    if not recipient:
        return

    current = recipient[0].status
    if not _should_update_status(current, status):
        return

    updates = {"status": status}
    now = now_datetime()
    if status == REC_STATUS_SENT:
        updates["sent_time"] = now
    elif status == REC_STATUS_DELIVERED:
        updates["delivered_time"] = now
    elif status == REC_STATUS_READ:
        updates["read_time"] = now

    frappe.db.set_value("Campaign Recipient", recipient[0].name, updates)


def _should_update_status(current, new_status):
    if not current:
        return True
    if current == REC_STATUS_READ:
        return False
    if new_status == REC_STATUS_FAILED:
        return current not in (REC_STATUS_DELIVERED, REC_STATUS_READ)

    order = {
        REC_STATUS_SENT: 1,
        REC_STATUS_DELIVERED: 2,
        REC_STATUS_READ: 3,
    }
    return order.get(new_status, 0) >= order.get(current, 0)


def _mark_event_error(event, message):
    event.error = message
    event.processed = 1
    event.processed_at = now_datetime()
    event.save(ignore_permissions=True)

from tap_buddy.services.redis_utils import push_to_queue, pop_from_queue_batch


# ---------------------------------------------------------------------------
# Status hierarchy: higher number wins when deduplicating a batch
# ---------------------------------------------------------------------------
_STATUS_RANK = {
    REC_STATUS_SENT: 1,
    REC_STATUS_DELIVERED: 2,
    REC_STATUS_READ: 3,
    # Failed is intentionally absent so it never promotes over a delivery status
}


def buffer_webhook_payload(payload, raw_body=None, signature=None):
    """
    O(1) ingestion: wraps each item in a typed envelope and pushes to Redis.

    Envelope format::

        {
            "payload":    {...},          # original webhook dict
            "signature":  "sha256=...",   # HMAC header value (or None)
            "received_at": "2026-...",    # ISO timestamp for audit
        }

    Using an envelope lets the batch processor distinguish the webhook body
    from metadata without parsing heuristics.
    """
    if not isinstance(payload, list):
        payload = [payload]

    ts = now_datetime()
    iso = ts.isoformat() if hasattr(ts, "isoformat") else str(ts)

    count = 0
    for item in payload:
        envelope = {
            "payload": item,
            "signature": signature,
            "received_at": iso,
        }
        push_to_queue("webhooks", envelope)
        count += 1

    return count


def process_webhook_batches(batch_size=2000):
    """
    Drain the Redis webhook queue, deduplicate by provider_message_id
    (keeping the highest-ranked delivery status), then bulk-write to the DB.

    Design:
    - Items with missing/unknown provider_message_id or status go to the DLQ
      via ``_route_to_dlq`` (injectable seam for testing).
    - Valid items are merged into a dict keyed by provider_message_id.
      When two events share the same ID, the higher-ranked status wins.
    - The final merged dict is flushed via ``_bulk_update_status``
      (injectable seam for testing).

    Returns the number of items popped from the queue.
    """
    items = pop_from_queue_batch("webhooks", batch_size)
    if not items:
        return 0

    deduped: dict = {}

    for item in items:
        # Unwrap envelope if present
        if isinstance(item, dict) and "payload" in item:
            inner = item["payload"]
        else:
            inner = item  # bare dict (legacy path)

        provider_message_id = _extract_provider_message_id(inner)
        status = _normalize_status(_extract_status(inner))

        if not provider_message_id or not status:
            _route_to_dlq(item, "Missing provider_message_id or unrecognised status")
            continue

        existing = deduped.get(provider_message_id)
        if existing is None:
            deduped[provider_message_id] = {"status": status, "item": item}
        else:
            # Keep whichever status ranks higher; Failed never beats a delivery status
            existing_rank = _STATUS_RANK.get(existing["status"], 0)
            new_rank = _STATUS_RANK.get(status, 0)
            if new_rank > existing_rank:
                deduped[provider_message_id] = {"status": status, "item": item}

    if deduped:
        _bulk_update_status(deduped)

    return len(items)


def _route_to_dlq(item, reason):
    """
    Send a poison/unresolvable item to the dead-letter queue.
    Logs without dumping raw payload to avoid PII leakage.
    """
    try:
        frappe.logger("tap_buddy_webhooks").error(
            f"Webhook DLQ: {reason} (item keys: {list(item.keys()) if isinstance(item, dict) else type(item).__name__})"
        )
    except Exception:
        pass
    from tap_buddy.services.redis_utils import get_redis_conn, PREFIX
    try:
        conn = get_redis_conn()
        conn.lpush(f"{PREFIX}queue:webhooks_dlq", frappe.as_json(item))
    except Exception:
        pass


def _bulk_update_status(deduped_map):
    """
    Apply the deduplicated status map to Message Logs and Campaign Recipients.

    ``deduped_map`` structure::

        {
            "<provider_message_id>": {
                "status": "Delivered",   # canonical status string
                "item":   {...},         # original envelope (for audit)
            },
            ...
        }
    """
    for provider_message_id, entry in deduped_map.items():
        status = entry["status"]
        message_log = _get_message_log(provider_message_id)
        if not message_log:
            continue
        _apply_status_to_message_log(message_log, status)
        if message_log.campaign and message_log.school:
            _apply_status_to_recipient(message_log.campaign, message_log.school, status)

