# -*- coding: utf-8 -*-
"""
Metrics and Observability for Delivery Status Synchronization Service.
Tracks counters, latencies, and batch processing throughput.
"""

from typing import Dict
import frappe


class DeliverySyncMetrics:
    """In-memory and Redis-backed metric collector."""

    @staticmethod
    def _get_key(metric_name: str) -> str:
        from tap_buddy.services.redis_utils import PREFIX
        return f"{PREFIX}metrics:delivery_sync:{metric_name}"

    @classmethod
    def increment_counter(cls, metric_name: str, count: int = 1) -> None:
        """Increment a metric counter in Redis."""
        try:
            from tap_buddy.services.redis_utils import get_redis_conn
            conn = get_redis_conn()
            conn.incrby(cls._get_key(metric_name), count)
        except Exception:
            pass

    @classmethod
    def record_latency(cls, metric_name: str, duration_ms: float) -> None:
        """Record batch processing latency."""
        try:
            from tap_buddy.services.redis_utils import get_redis_conn
            conn = get_redis_conn()
            key = cls._get_key(f"{metric_name}:latency_sum")
            cnt_key = cls._get_key(f"{metric_name}:latency_count")
            conn.incrbyfloat(key, duration_ms)
            conn.incr(cnt_key)
        except Exception:
            pass

    @classmethod
    def get_snapshot(cls) -> Dict[str, float]:
        """Fetch snapshot of all synchronization metrics."""
        try:
            from tap_buddy.services.redis_utils import get_redis_conn
            conn = get_redis_conn()
            keys = [
                "events_received",
                "events_processed",
                "events_failed",
                "events_dlq",
                "message_logs_updated",
                "recipients_updated",
            ]
            snapshot = {}
            for k in keys:
                val = conn.get(cls._get_key(k))
                snapshot[k] = int(val) if val else 0
            return snapshot
        except Exception:
            return {}
