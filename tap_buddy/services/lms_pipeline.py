"""LMS pipeline runner (stub).

Provides `run_lms_pipeline` which orchestrates a safe, local-only
polling run. This is intentionally lightweight so it can be executed
during CI or local tests without network access.
"""
from typing import Dict


def run_lms_pipeline(limit: int = 20, process_pending: bool = False) -> Dict[str, object]:
    """Run a dry LMS pipeline that does not call external services.

    Returns a summary dict to mimic the real runner's shape.
    """
    return {"status": "ok", "ingested": 0, "processed_pending": False}
