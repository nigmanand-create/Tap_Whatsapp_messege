import frappe

from tap_buddy.services.lms_ingestion import process_lms_event
from tap_buddy.services.webhook_processor import process_webhook_event


def replay_webhook_event(event_name, force=False):
    event = frappe.get_doc("Webhook Event", event_name)
    if event.processed and not force and not event.error:
        return {"status": "skipped", "reason": "already_processed"}

    event.processed = 0
    event.error = None
    event.processed_at = None
    event.save(ignore_permissions=True)

    process_webhook_event(event.name)
    event.reload()

    return {
        "status": "processed" if event.processed else "pending",
        "error": event.error,
    }


def replay_lms_event(log_name, force=False):
    log = frappe.get_doc("LMS Trigger Log", log_name)
    if log.status == "Processed" and log.campaign and not force:
        return {"status": "skipped", "reason": "already_processed"}

    log.status = "Pending"
    log.error = None
    log.processed_at = None
    log.save(ignore_permissions=True)

    process_lms_event(log.name)
    log.reload()

    return {
        "status": log.status,
        "campaign": log.campaign,
        "error": log.error,
    }


def replay_failed_webhook_events(limit=50):
    rows = frappe.get_all(
        "Webhook Event",
        filters={"processed": 1, "error": ["!=", ""]},
        fields=["name"],
        limit=limit,
        order_by="modified asc",
    )
    results = []
    for row in rows:
        results.append(replay_webhook_event(row.name, force=True))
    return results


def replay_failed_lms_events(limit=50):
    rows = frappe.get_all(
        "LMS Trigger Log",
        filters={"status": ["in", ["Failed", "Skipped"]]},
        fields=["name"],
        limit=limit,
        order_by="modified asc",
    )
    results = []
    for row in rows:
        results.append(replay_lms_event(row.name, force=True))
    return results
