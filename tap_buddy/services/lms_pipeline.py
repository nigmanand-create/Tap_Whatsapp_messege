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
    # Ensure settings loaded from env are applied to the site single (optional)
    try:
        # If env contains values, apply them to site so other parts of app use them.
        from tap_buddy.ops import apply_literal_lms

        apply_literal_lms()
    except Exception:
        # non-fatal; continue
        pass

    res = poll_lms_students(limit=limit)

    if process_pending:
        process_pending_lms_events()

    return res
