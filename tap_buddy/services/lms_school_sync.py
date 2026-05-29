"""
lms_school_sync.py
==================
Syncs Schools from the LMS API into TAP Buddy.

Flow:
  1. Fetch all LMS School records
  2. Create or update TAP Buddy ``School`` doctype entries (matched by lms_id)
  3. Re-link ``LMS Student.school`` field for students whose school_id now resolves

Called by:
  - scheduler.py  (hourly, before student sync)
  - Manual: bench execute tap_buddy.tasks.scheduler.sync_lms_schools
"""

import frappe
from frappe.utils import now_datetime

from tap_buddy.services.lms_client import LMSClient, LMSAPIError


LMS_SCHOOL_FIELDS = ["name", "name1", "headmaster_name", "headmaster_phone", "status", "city", "state"]


@frappe.whitelist()
def sync_all_schools():
    """Pull all schools from LMS and upsert into TAP Buddy School doctype.

    Returns summary dict::
        {"status": "ok", "total_fetched": 1, "created": 0, "updated": 1, "errors": 0}
    """
    client = LMSClient()
    try:
        schools = client.get_all_resource("School", fields=LMS_SCHOOL_FIELDS)
    except LMSAPIError as e:
        frappe.log_error(title="LMS School Sync — API Error", message=str(e))
        return {"status": "error", "error": str(e)}

    if not schools:
        return {"status": "ok", "total_fetched": 0, "created": 0, "updated": 0, "errors": 0}

    stats = {"total_fetched": len(schools), "created": 0, "updated": 0, "errors": 0}

    for raw in schools:
        try:
            result = _upsert_school(raw)
            stats[result] += 1
        except Exception:
            stats["errors"] += 1
            frappe.log_error(title="LMS School Sync — Upsert Error", message=frappe.get_traceback())

    # After schools are synced, backfill student.school links
    try:
        backfill_count = _backfill_student_schools()
        stats["students_linked"] = backfill_count
    except Exception:
        frappe.log_error(title="LMS School Sync — Backfill Error", message=frappe.get_traceback())
        stats["students_linked"] = 0

    frappe.logger("lms_sync").info(f"LMS School Sync: {stats}")
    return {"status": "ok", **stats}


def _upsert_school(raw: dict) -> str:
    """Create or update a TAP Buddy School from an LMS School record.

    LMS name1 = Display name  (e.g. "Test School 12711")
    LMS name  = System name   (e.g. "Test-SC12711") — used as lms_id
    """
    lms_id     = raw.get("name")             # system name like Test-SC12711
    school_nm  = raw.get("name1") or lms_id  # display name
    hm_name    = raw.get("headmaster_name") or ""
    hm_phone   = raw.get("headmaster_phone") or ""
    lms_status = raw.get("status") or ""

    if not lms_id:
        return "errors"

    # Try to find existing School by lms_id
    existing = frappe.get_value("School", {"lms_id": lms_id}, "name")

    if existing:
        doc = frappe.get_doc("School", existing)
        doc.update({
            "principal_name":    hm_name or doc.get("principal_name"),
            "lms_school_status": lms_status,
        })
        doc.save(ignore_permissions=True)
        return "updated"
    else:
        # Create new School — whatsapp_number is now optional
        new_values: dict = {
            "school_name":       school_nm,
            "lms_id":            lms_id,
            "principal_name":    hm_name,
            "lms_school_status": lms_status,
        }
        if hm_phone:
            new_values["whatsapp_number"] = hm_phone
        doc = frappe.new_doc("School")
        doc.update(new_values)
        doc.insert(ignore_permissions=True)
        return "created"


def _backfill_student_schools() -> int:
    """Link LMS Student.school for students where school is blank but lms_school_id is stored.

    Runs after school sync so School.lms_id is populated.
    Uses Python-side resolution — no raw SQL JOIN needed.
    """
    # Build lms_school_id → School.name lookup map
    all_schools = frappe.get_all("School", fields=["name", "lms_id"])
    school_map = {s["lms_id"]: s["name"] for s in all_schools if s.get("lms_id")}

    if not school_map:
        return 0

    # Students missing school link but with a stored lms_school_id
    students_to_link = frappe.get_all(
        "LMS Student",
        filters={"school": ("in", ["", None])},
        fields=["name", "lms_school_id"],
    )

    linked = 0
    for row in students_to_link:
        raw_school_id = (row.get("lms_school_id") or "").strip()
        if not raw_school_id:
            continue
        school_name = school_map.get(raw_school_id)
        if not school_name:
            continue
        frappe.db.set_value("LMS Student", row["name"], "school", school_name, update_modified=False)
        linked += 1

    if linked:
        frappe.db.commit()

    return linked


def check_enrollment_permission():
    """Diagnostic: check if Enrollment API is accessible.

    Returns a dict with status and guidance for the admin.
    """
    client = LMSClient()
    try:
        resp = client.get_resource("Enrollment", fields=["name"], limit_page_length=1)
        return {
            "status": "accessible",
            "message": "Enrollment API is accessible. Sync can be enabled.",
            "sample": resp.get("data", [])[:1],
        }
    except LMSAPIError as e:
        err_str = str(e)
        if "403" in err_str:
            return {
                "status": "permission_denied",
                "message": (
                    "Enrollment API returned 403 Forbidden. "
                    "Action required: Ask LMS admin to grant READ permission on "
                    "'Enrollment' doctype for the TAP Buddy API user. "
                    "Once granted, Enrollment sync will activate automatically."
                ),
                "http_code": 403,
            }
        return {"status": "error", "message": err_str}
