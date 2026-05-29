"""
lms_batch_sync.py
=================
Syncs Batch records from LMS into TAP Buddy's ``LMS Batch`` doctype.

Flow:
  1. Fetch all Batch records from LMS API
  2. Create/update LMS Batch (keyed by lms_id = batch name like 1-BT0205)
  3. Resolve school link via school_id if available
  4. Returns sync stats

Enables:
  - Campaign targeting: "all students in batch X"
  - Assignment polling: use current_week to detect missing submissions
"""

import frappe
from frappe.utils import now_datetime

from tap_buddy.services.lms_client import LMSClient, LMSAPIError


LMS_BATCH_FIELDS = [
    "name", "name1", "title", "active", "batch_id",
    "start_date", "end_date", "program_type",
    "total_weeks", "current_calendar_week",
]


@frappe.whitelist()
def sync_all_batches():
    """Pull all batches from LMS and upsert into LMS Batch doctype.

    Returns::
        {"status": "ok", "total_fetched": 1, "created": 0, "updated": 1, "errors": 0}
    """
    client = LMSClient()
    try:
        batches = client.get_all_resource("Batch", fields=LMS_BATCH_FIELDS)
    except LMSAPIError as e:
        frappe.log_error(title="LMS Batch Sync — API Error", message=str(e))
        return {"status": "error", "error": str(e)}

    stats = {"total_fetched": len(batches), "created": 0, "updated": 0, "skipped": 0, "errors": 0}

    for raw in batches:
        try:
            result = _upsert_batch(raw)
            stats[result] += 1
        except Exception:
            stats["errors"] += 1
            frappe.log_error(title="LMS Batch Sync — Upsert Error", message=frappe.get_traceback())

    frappe.logger("lms_sync").info(f"LMS Batch Sync: {stats}")
    return {"status": "ok", **stats}


def _upsert_batch(raw: dict) -> str:
    lms_id     = raw.get("name")          # e.g. "1-BT0205"
    batch_name = raw.get("name1") or lms_id
    is_active  = bool(raw.get("active", 1))

    if not lms_id:
        return "skipped"

    existing = frappe.db.exists("LMS Batch", lms_id)

    if existing:
        doc = frappe.get_doc("LMS Batch", lms_id)
        doc.update({
            "batch_name":     batch_name,
            "title":          raw.get("title") or doc.get("title"),
            "program_type":   raw.get("program_type") or doc.get("program_type"),
            "is_active":      is_active,
            "current_week":   raw.get("current_calendar_week") or doc.get("current_week"),
            "total_weeks":    raw.get("total_weeks") or doc.get("total_weeks"),
            "start_date":     raw.get("start_date") or doc.get("start_date"),
            "end_date":       raw.get("end_date") or doc.get("end_date"),
            "last_synced_at": now_datetime(),
        })
        doc.save(ignore_permissions=True)
        return "updated"
    else:
        doc = frappe.new_doc("LMS Batch")
        doc.update({
            "lms_id":        lms_id,
            "batch_name":    batch_name,
            "title":         raw.get("title") or "",
            "program_type":  raw.get("program_type") or "",
            "is_active":     is_active,
            "current_week":  raw.get("current_calendar_week") or 0,
            "total_weeks":   raw.get("total_weeks") or 0,
            "start_date":    raw.get("start_date") or None,
            "end_date":      raw.get("end_date") or None,
            "last_synced_at": now_datetime(),
        })
        doc.insert(ignore_permissions=True)
        return "created"


def get_active_batches() -> list[dict]:
    """Return all active batches with their current week info."""
    return frappe.get_all(
        "LMS Batch",
        filters={"is_active": 1},
        fields=["lms_id", "batch_name", "current_week", "total_weeks", "school"],
    )


def get_batch(lms_batch_id: str) -> dict | None:
    """Fetch a single LMS Batch by its LMS ID."""
    result = frappe.get_all(
        "LMS Batch",
        filters={"lms_id": lms_batch_id},
        fields=["lms_id", "batch_name", "current_week", "school", "is_active"],
        limit=1,
    )
    return result[0] if result else None
