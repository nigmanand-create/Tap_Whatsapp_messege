"""Service package stubs for tap_buddy.

These are minimal implementations to restore imports and enable tests
and operations when full service sources are not present. Replace with
real implementations when available.
"""

from .lms_client import LMSClient
from .lms_ingestion import poll_lms_students
from .lms_pipeline import run_lms_pipeline
from .recipients import build_campaign_recipients

__all__ = [
    "LMSClient",
    "poll_lms_students",
    "run_lms_pipeline",
    "build_campaign_recipients",
]
