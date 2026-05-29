"""
lms_automation_engine.py
========================
WhatsApp automation dispatch layer for LMS events.

Responsibilities:
  1. Receive reminder events from lms_assignment_polling.py
  2. Check dedup via LMS Reminder Log (prevent duplicate sends)
  3. Build HSM template parameters from context
  4. Send via GlificClient.send_message_with_hsm_fallback()
  5. Log result to LMS Reminder Log

Template mapping (using approved pta_meeting_alert_v2):
  {{1}} → parent_name  (student_name as proxy)
  {{2}} → student_name
  {{3}} → context description  (e.g. "Week 3 Assignment")
  {{4}} → action string        (e.g. "Submit before Sunday")

Architecture:
  - STATELESS per call — all state lives in LMS Reminder Log
  - Retry-safe: dedup key prevents double sends
  - Exception-safe: errors logged, never crash the polling loop
"""

import frappe
import json
from frappe.utils import now_datetime

from tap_buddy.services.glific_client import GlificClient, GlificAPIError, GlificTerminalError


REMINDER_TEMPLATE  = "pta_meeting_alert_v2"   # approved HSM template
FALLBACK_FREE_TEXT = False                     # never send free-text outside 24hr window


# ─── Public API ──────────────────────────────────────────────────────────────

def dispatch_reminder(
    student_id: str,
    student_name: str,
    phone: str,
    reminder_type: str,
    dedup_key: str,
    context: dict | None = None,
) -> str:
    """Send a WhatsApp reminder if not already sent (dedup via LMS Reminder Log).

    Args:
        student_id:    LMS Student ID (e.g. ST00000206)
        student_name:  Display name for the message
        phone:         WhatsApp phone number (normalized)
        reminder_type: Event type (ASSIGNMENT_DUE_SOON, ASSIGNMENT_OVERDUE, etc.)
        dedup_key:     Unique key to prevent duplicate sends
        context:       Extra context dict (batch_id, week, etc.)

    Returns:
        "sent"    — message dispatched successfully
        "skipped" — already sent (dedup hit)
        "failed"  — error during send
    """
    # ── Dedup check ──────────────────────────────────────────────────────────
    if _already_sent(dedup_key):
        frappe.logger("lms_automation").debug(
            f"[DEDUP] Skipping {reminder_type} for {student_id} — already sent ({dedup_key})"
        )
        return "skipped"

    # ── Build HSM parameters ─────────────────────────────────────────────────
    params = _build_template_params(student_name, reminder_type, context or {})

    # ── Send via Glific ───────────────────────────────────────────────────────
    glific_message_id = None
    error_msg = None
    status = "Sent"

    try:
        client = GlificClient()
        resp = client.send_hsm_message(
            phone=phone,
            template_id=REMINDER_TEMPLATE,
            parameters=params,
        )
        glific_message_id = _extract_message_id(resp)
        frappe.logger("lms_automation").info(
            f"[SENT] {reminder_type} → {phone} ({student_id}) "
            f"glific_id={glific_message_id}"
        )
    except GlificTerminalError as e:
        # Non-retryable (wrong phone, opted-out, etc.)
        error_msg = f"Terminal: {e}"
        status = "Failed"
        frappe.log_error(
            title=f"LMS Automation — Terminal Error ({reminder_type})",
            message=f"student={student_id} phone={phone}\n{e}"
        )
    except GlificAPIError as e:
        # Transient — log but don't mark as sent (will retry next poll)
        error_msg = f"Transient: {e}"
        status = "Failed"
        frappe.log_error(
            title=f"LMS Automation — API Error ({reminder_type})",
            message=f"student={student_id} phone={phone}\n{e}"
        )
    except Exception:
        error_msg = frappe.get_traceback()
        status = "Failed"
        frappe.log_error(
            title=f"LMS Automation — Unexpected Error ({reminder_type})",
            message=frappe.get_traceback()
        )

    # ── Log to LMS Reminder Log ───────────────────────────────────────────────
    _log_reminder(
        student_id=student_id,
        phone=phone,
        reminder_type=reminder_type,
        dedup_key=dedup_key,
        status=status,
        glific_message_id=glific_message_id,
        context=context or {},
        error=error_msg,
    )

    return "sent" if status == "Sent" else "failed"


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _already_sent(dedup_key: str) -> bool:
    """Return True if a Sent reminder log already exists for this dedup_key."""
    return bool(
        frappe.db.exists(
            "LMS Reminder Log",
            {"dedup_key": dedup_key, "status": "Sent"}
        )
    )


def _build_template_params(student_name: str, reminder_type: str, context: dict) -> list[str]:
    """Build the 4 HSM template parameters from event context.

    Template slots:
        {{1}} parent_name   → student_name (parent proxy)
        {{2}} student_name  → student_name
        {{3}} event_desc    → human-readable event description
        {{4}} action        → what the parent/student should do
    """
    week      = context.get("week", "")
    batch_nm  = context.get("batch_name", "your batch")

    if reminder_type == "ASSIGNMENT_DUE_SOON":
        event_desc = f"Week {week} assignment in {batch_nm}"
        action     = "Please submit it before the deadline"
    elif reminder_type == "ASSIGNMENT_OVERDUE":
        event_desc = f"Week {week} assignment in {batch_nm}"
        action     = "Assignment is overdue. Please submit now"
    elif reminder_type == "ASSIGNMENT_CREATED":
        event_desc = f"A new assignment has been posted in {batch_nm}"
        action     = "Please check and complete it this week"
    elif reminder_type == "QUIZ_REMINDER":
        event_desc = f"Quiz for week {week} in {batch_nm}"
        action     = "Please attempt the quiz today"
    else:
        event_desc = f"Update from {batch_nm}"
        action     = "Please log in to check"

    return [student_name, student_name, event_desc, action]


def _log_reminder(
    student_id: str,
    phone: str,
    reminder_type: str,
    dedup_key: str,
    status: str,
    glific_message_id: str | None,
    context: dict,
    error: str | None,
):
    """Write a record to LMS Reminder Log for auditing and dedup."""
    try:
        log = frappe.new_doc("LMS Reminder Log")
        log.student_id         = student_id
        log.phone              = phone
        log.reminder_type      = reminder_type
        log.dedup_key          = dedup_key
        log.status             = status
        log.glific_message_id  = glific_message_id or ""
        log.sent_at            = now_datetime()
        log.context_json       = json.dumps(context, default=str)
        log.error              = error or ""
        log.insert(ignore_permissions=True)
    except Exception:
        # Never crash the caller due to logging failure
        frappe.log_error(
            title="LMS Reminder Log — Write Error",
            message=frappe.get_traceback()
        )


def _extract_message_id(resp) -> str | None:
    """Extract message ID from Glific HSM response."""
    if not resp:
        return None
    if isinstance(resp, dict):
        # Try common paths
        msg = (
            resp.get("id")
            or resp.get("message_id")
            or (resp.get("data") or {}).get("sendHsmMessage", {}).get("message", {}).get("id")
        )
        return str(msg) if msg else None
    return None
