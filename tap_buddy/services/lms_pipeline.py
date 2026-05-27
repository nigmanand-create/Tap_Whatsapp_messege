import frappe
import os

from tap_buddy.services.lms_ingestion import poll_lms_students, process_pending_lms_events


def run_lms_pipeline(limit=100, process_pending=False):
    """Run the LMS poll pipeline.

    - Polls the LMS for students (uses site settings or env vars `LMS_BASE_URL`/`LMS_API_KEY`).
    - Optionally processes pending LMS Trigger Log entries.

    Usage:
      bench --site tapbuddy.local execute "tap_buddy.services.lms_pipeline.run_lms_pipeline(50, True)"
    """
    # If env vars are present, sync them into the Frappe single doc so other
    # parts of the app (LMSClient) pick them up via frappe.get_single().
    try:
        from tap_buddy.ops import apply_lms_from_env

        apply_lms_from_env()
    except Exception:
        # non-fatal; continue with whatever is already in site settings
        pass

    res = poll_lms_students(limit=limit)

    if process_pending:
        process_pending_lms_events()

    return res
