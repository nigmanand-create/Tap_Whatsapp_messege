import frappe
from frappe.utils import now_datetime

from tap_buddy.services.lms_mapper import handle_lms_event
from tap_buddy.utils.constants import QUEUE_SHORT
from tap_buddy.services.lms_client import LMSClient, LMSAPIError


def enqueue_lms_events(payload, raw_body=None, signature=None, source="lms"):
    event_names = []
    items = payload if isinstance(payload, list) else [payload]

    for item in items:
        event_name = _create_log(item, raw_body, signature, source)
        if not event_name:
            continue
        event_names.append(event_name)
        frappe.enqueue(
            "tap_buddy.services.lms_ingestion.process_lms_event",
            queue=QUEUE_SHORT,
            job_name=f"tap_buddy_lms_{event_name}",
            log_name=event_name,
        )

    return event_names


def process_pending_lms_events(limit=100):
    pending = frappe.get_all(
        "LMS Trigger Log",
        filters={"status": "Pending"},
        fields=["name"],
        limit=limit,
        order_by="creation asc",
    )

    for row in pending:
        process_lms_event(row.name)


def process_lms_event(log_name):
    log = frappe.get_doc("LMS Trigger Log", log_name)
    if log.status != "Pending":
        return

    payload = _parse_payload(log.payload)
    event_type = log.event_type or _extract_event_type(payload)
    event_id = log.event_id or _extract_event_id(payload)

    if not event_type:
        _mark_log(log, "Failed", "Missing event_type")
        return

    log.event_type = event_type
    if event_id:
        log.event_id = event_id

    outcome = handle_lms_event(log, payload)
    status = outcome.get("status") or "Processed"
    log.status = status
    log.processed_at = now_datetime()
    log.mapping = outcome.get("mapping")
    log.campaign = outcome.get("campaign")
    log.error = outcome.get("error")
    log.save(ignore_permissions=True)


def _create_log(payload, raw_body=None, signature=None, source="lms"):
    event_type = _extract_event_type(payload)
    event_id = _extract_event_id(payload)

    if event_id:
        existing = frappe.get_all(
            "LMS Trigger Log",
            filters={"event_id": event_id},
            fields=["name"],
            limit=1,
        )
        if existing:
            return existing[0].name

    log = frappe.new_doc("LMS Trigger Log")
    log.event_id = event_id
    log.event_type = event_type
    log.source = source
    log.signature = signature
    log.payload = frappe.as_json(payload)
    log.received_at = now_datetime()
    log.status = "Pending"
    log.insert(ignore_permissions=True)
    return log.name


def _parse_payload(payload_text):
    if not payload_text:
        return {}
    if isinstance(payload_text, dict):
        return payload_text
    return frappe.parse_json(payload_text)


def _extract_event_type(payload):
    for key in ("event_type", "event", "type"):
        value = _read_payload_value(payload, key)
        if value:
            return str(value)
    return None


def _extract_event_id(payload):
    for key in ("event_id", "eventId", "id"):
        value = _read_payload_value(payload, key)
        if value:
            return str(value)
    return None


def _read_payload_value(payload, key):
    if not isinstance(payload, dict):
        return None
    if key in payload:
        return payload.get(key)
    if "data" in payload and isinstance(payload["data"], dict):
        return payload["data"].get(key)
    return None


def _mark_log(log, status, message):
    log.status = status
    log.error = message
    log.processed_at = now_datetime()
    log.save(ignore_permissions=True)


def poll_lms_students(limit=20, fields=None, filters=None):
    """Poll the configured LMS for Student records and enqueue them as LMS events.

    - Uses `LMS Integration Settings.lms_base_url` and `.lms_api_key`.
    - Enqueues each student record via `enqueue_lms_events` so existing processing is reused.
    """
    settings = frappe.get_single("LMS Integration Settings")
    if not settings.polling_enabled:
        return {"status": "disabled"}

    client = LMSClient()
    try:
        resp = client.get_students(fields=fields, limit_page_length=limit, filters=filters)
    except LMSAPIError as e:
        frappe.log_error(title="LMS Polling Error", message=str(e))
        return {"status": "error", "error": str(e)}

    # Frappe-style resource responses often return a top-level `data` list
    records = resp.get("data") if isinstance(resp, dict) and "data" in resp else resp
    if not records:
        # update last polled timestamp even if no records
        settings.last_polled_at = now_datetime()
        settings.save(ignore_permissions=True)
        return {"status": "ok", "processed": 0}

    processed = 0
    for rec in records:
        # enqueue each record using existing ingestion path
        try:
            enqueue_lms_events(rec, raw_body=None, signature=None, source="lms_poll")
            processed += 1
        except Exception:
            frappe.log_error(title="LMS Enqueue Error", message=frappe.get_traceback())

    settings.last_polled_at = now_datetime()
    settings.save(ignore_permissions=True)

    return {"status": "ok", "processed": processed}
