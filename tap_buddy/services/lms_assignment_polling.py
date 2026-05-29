"""
lms_assignment_polling.py
=========================
Polls LMS Assignment + Submission APIs to detect missing submissions
and generate WhatsApp reminder events.

Event Types Generated:
  - ASSIGNMENT_DUE_SOON   : student has not submitted in current active batch week
  - ASSIGNMENT_OVERDUE    : student missed last week (configurable)
  - ASSIGNMENT_CREATED    : new assignment detected since last poll

Architecture:
  - Polling is STATELESS per run; uses LMS Reminder Log for dedup
  - Does NOT store Assignment records locally (avoids stale data)
  - Events are queued to lms_automation_engine for WhatsApp dispatch

Called by:
  - scheduler.py every 30 minutes
"""

import frappe
from frappe.utils import now_datetime, add_days, getdate, today

from tap_buddy.services.lms_client import LMSClient, LMSAPIError
from tap_buddy.services.lms_batch_sync import get_active_batches


SUBMISSION_FIELDS = ["name", "assign_id", "student_id", "status", "week", "created_at"]
ASSIGNMENT_FIELDS = ["name", "assignment_name", "assignment_type", "difficulty_tier"]


# ─── Public API ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def poll_assignment_events():
    """Main polling entry point. Detects events and queues reminders.

    Returns::
        {
          "status": "ok",
          "batches_checked": 1,
          "events_generated": 3,
          "reminders_sent": 2,
          "skipped_dedup": 1,
        }
    """
    client = LMSClient()
    active_batches = get_active_batches()

    if not active_batches:
        frappe.logger("lms_poll").info("No active batches found. Skipping assignment poll.")
        return {"status": "ok", "batches_checked": 0, "events_generated": 0}

    total_events = 0
    total_sent = 0
    total_skipped = 0

    for batch in active_batches:
        current_week = batch.get("current_week") or 0
        if current_week <= 0:
            continue

        try:
            events, sent, skipped = _process_batch(client, batch, current_week)
            total_events  += events
            total_sent    += sent
            total_skipped += skipped
        except Exception:
            frappe.log_error(
                title=f"LMS Assignment Poll — Batch {batch['lms_id']} Error",
                message=frappe.get_traceback()
            )

    result = {
        "status": "ok",
        "batches_checked": len(active_batches),
        "events_generated": total_events,
        "reminders_sent": total_sent,
        "skipped_dedup": total_skipped,
    }
    frappe.logger("lms_poll").info(f"Assignment poll result: {result}")
    return result


# ─── Batch-level processing ──────────────────────────────────────────────────

def _process_batch(client: LMSClient, batch: dict, current_week: int) -> tuple[int, int, int]:
    """Check all synced students for missing submissions in current_week."""
    batch_id  = batch["lms_id"]
    events = sent = skipped = 0

    # Fetch all submissions for this week from LMS
    submitted_student_ids = _get_submitted_students(client, current_week)

    # Get all active students from our local sync
    all_students = frappe.get_all(
        "LMS Student",
        filters={"lms_status": ("in", ["active", "Active", ""])},
        fields=["lms_id", "student_name", "phone"],
    )

    for student in all_students:
        if not student.get("phone"):
            continue

        student_lms_id = student["lms_id"]

        if student_lms_id in submitted_student_ids:
            continue   # already submitted — no reminder needed

        # Generate ASSIGNMENT_DUE_SOON event
        dedup_key = f"{student_lms_id}:ASSIGNMENT_DUE_SOON:{batch_id}:W{current_week}"
        events += 1

        # Import here to avoid circular imports
        from tap_buddy.services.lms_automation_engine import dispatch_reminder
        result = dispatch_reminder(
            student_id   = student_lms_id,
            student_name = student["student_name"],
            phone        = student["phone"],
            reminder_type = "ASSIGNMENT_DUE_SOON",
            dedup_key    = dedup_key,
            context      = {
                "batch_id":     batch_id,
                "batch_name":   batch.get("batch_name", ""),
                "week":         current_week,
            },
        )

        if result == "sent":
            sent += 1
        elif result == "skipped":
            skipped += 1

    return events, sent, skipped


def _get_submitted_students(client: LMSClient, week: int) -> set:
    """Fetch student IDs who have submitted for the given week."""
    try:
        resp = client.get_all_resource(
            "Submission",
            fields=["student_id", "week", "status"],
        )
        submitted = {
            r["student_id"]
            for r in resp
            if r.get("week") == week and r.get("student_id")
        }
        return submitted
    except LMSAPIError:
        frappe.log_error(title="LMS Submission Fetch Error", message=frappe.get_traceback())
        return set()


def get_new_assignments(client: LMSClient, since_name: str | None = None) -> list[dict]:
    """Fetch new assignments from LMS since last known assignment name.

    Used to generate ASSIGNMENT_CREATED events.
    """
    assignments = client.get_all_resource("Assignment", fields=ASSIGNMENT_FIELDS)
    if since_name:
        # Return only ones not yet seen (simple name-based detection)
        known = {
            r["event_id"]
            for r in frappe.get_all(
                "LMS Trigger Log",
                filters={"event_type": "ASSIGNMENT_CREATED"},
                fields=["event_id"],
            )
        }
        assignments = [a for a in assignments if a.get("name") not in known]
    return assignments


def detect_overdue_students(client: LMSClient, week: int) -> list[dict]:
    """Find students who missed last week's submission (week - 1)."""
    if week <= 1:
        return []
    last_week = week - 1
    submitted_last_week = _get_submitted_students(client, last_week)
    all_students = frappe.get_all(
        "LMS Student",
        filters={"lms_status": ("in", ["active", "Active", ""])},
        fields=["lms_id", "student_name", "phone"],
    )
    return [s for s in all_students if s["lms_id"] not in submitted_last_week and s.get("phone")]
