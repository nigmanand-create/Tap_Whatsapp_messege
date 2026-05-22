"""Minimal LMS ingestion stub.

This module provides a no-op polling function used by the pipeline runner.
"""
from typing import List


def poll_lms_students(limit: int = 20) -> List[dict]:
    """Poll LMS for students. Stub returns empty list."""
    return []
