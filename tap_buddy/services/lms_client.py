"""Minimal LMS client stub.

Provides a safe, non-networking LMSClient used by tests and dry-runs.
Replace with the real HTTP-backed client when ready.
"""
from typing import List


class LMSClient:
    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = base_url
        self.api_key = api_key

    def get_students(self, limit: int = 20) -> List[dict]:
        """Return an empty list by default (safe stub)."""
        return []
