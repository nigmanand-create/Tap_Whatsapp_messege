"""
lms_student_sync.py
====================
Syncs Students from the LMS API into TAP Buddy.

What it does:
  1. Fetches all students from LMS (paginated automatically)
  2. For each student: creates or updates an ``LMS Student`` record
  3. Normalizes phone numbers (adds 91 country code if missing)
  4. Maps LMS school_id → TAP Buddy School (if available)
  5. Logs sync result to ``LMS Integration Settings``

Called by:
  - scheduler.py  (hourly cron)
  - Manual: frappe.call('tap_buddy.services.lms_student_sync.sync_all_students')
"""

import frappe
from frappe.utils import now_datetime

from tap_buddy.services.lms_client import LMSClient, LMSAPIError
from tap_buddy.utils.phone import normalize_phone_number


# ─── Public API ──────────────────────────────────────────────────────────────

@frappe.whitelist()
def sync_all_students():
    """Pull all students from LMS and upsert them into TAP Buddy.

    Returns a summary dict::
        {
            "status": "ok",
            "total_fetched": 150,
            "created": 12,
            "updated": 138,
            "skipped": 0,
            "errors": 0,
        }
    """
    settings = frappe.get_single("LMS Integration Settings")
    if not getattr(settings, "polling_enabled", False):
        return {"status": "disabled"}

    client = LMSClient()
    try:
        students = client.get_all_students()
    except LMSAPIError as e:
        frappe.log_error(title="LMS Student Sync — API Error", message=str(e))
        return {"status": "error", "error": str(e)}

    stats = {"total_fetched": len(students), "created": 0, "updated": 0, "skipped": 0, "errors": 0}

    for raw in students:
        try:
            result = _upsert_student(raw)
            stats[result] += 1
        except Exception:
            stats["errors"] += 1
            frappe.log_error(
                title="LMS Student Sync — Upsert Error",
                message=frappe.get_traceback()
            )

    # Update last sync timestamp
    settings.last_polled_at = now_datetime()
    settings.save(ignore_permissions=True)

    frappe.logger("lms_sync").info(
        f"LMS Student Sync complete: {stats}"
    )
    return {"status": "ok", **stats}


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _upsert_student(raw: dict) -> str:
    """Create or update an ``LMS Student`` doc. Returns 'created'/'updated'/'skipped'."""
    lms_id = raw.get("name")
    if not lms_id:
        return "skipped"

    phone_raw = raw.get("phone") or ""
    phone = normalize_phone_number(phone_raw) if phone_raw else None

    if not phone:
        return "skipped"   # No usable phone — cannot send WhatsApp

    school_link = _resolve_school(raw.get("school_id"))

    existing = frappe.get_all(
        "LMS Student",
        filters={"lms_id": lms_id},
        fields=["name"],
        limit=1,
    )

    if existing:
        doc = frappe.get_doc("LMS Student", existing[0].name)
        doc.update({
            "student_name":  raw.get("name1") or doc.get("student_name"),
            "phone":         phone,
            "glific_id":     raw.get("glific_id") or doc.get("glific_id"),
            "grade":         raw.get("grade") or doc.get("grade"),
            "section":       raw.get("section") or doc.get("section"),
            "gender":        raw.get("gender") or doc.get("gender"),
            "lms_status":    raw.get("status") or doc.get("lms_status"),
            "school":        school_link or doc.get("school"),
            "lms_school_id": raw.get("school_id") or doc.get("lms_school_id"),
            "last_synced_at": now_datetime(),
        })
        doc.save(ignore_permissions=True)
        return "updated"
    else:
        doc = frappe.new_doc("LMS Student")
        doc.update({
            "lms_id":        lms_id,
            "student_name":  raw.get("name1") or lms_id,
            "phone":         phone,
            "glific_id":     raw.get("glific_id") or "",
            "grade":         raw.get("grade") or "",
            "section":       raw.get("section") or "",
            "gender":        raw.get("gender") or "",
            "lms_status":    raw.get("status") or "Active",
            "school":        school_link or "",
            "lms_school_id": raw.get("school_id") or "",
            "last_synced_at": now_datetime(),
        })
        doc.insert(ignore_permissions=True)
        return "created"


# Cache school mappings for a single sync run to avoid repeated DB hits
_school_cache: dict[str, str] = {}


def _resolve_school(lms_school_id: str | None) -> str | None:
    """Map LMS school_id → TAP Buddy School docname.

    Lookup order:
    1. School.lms_id field (set by school sync)
    2. School.school_name exact match
    3. Direct School.name match
    """
    if not lms_school_id:
        return None
    if lms_school_id in _school_cache:
        return _school_cache[lms_school_id]

    # 1. Match by lms_id (populated after lms_school_sync runs)
    match = frappe.get_value("School", {"lms_id": lms_school_id}, "name")
    if not match:
        # 2. Match by school_name
        match = frappe.get_value("School", {"school_name": lms_school_id}, "name")
    if not match:
        # 3. Direct name match
        match = frappe.db.exists("School", lms_school_id)

    _school_cache[lms_school_id] = match or ""
    return match or None


def get_students_for_campaign(school=None, grade=None, active_only=True) -> list[dict]:
    """Fetch synced LMS students that are eligible for a campaign.

    Args:
        school:      TAP Buddy School docname (optional filter)
        grade:       Grade string e.g. '6' (optional filter)
        active_only: If True, only include students with lms_status='Active'

    Returns:
        List of dicts with keys: lms_id, student_name, phone, glific_id, school
    """
    filters = {}
    if school:
        filters["school"] = school
    if grade:
        filters["grade"] = grade
    if active_only:
        filters["lms_status"] = "Active"

    return frappe.get_all(
        "LMS Student",
        filters=filters,
        fields=["lms_id", "student_name", "phone", "glific_id", "school", "grade"],
    )
