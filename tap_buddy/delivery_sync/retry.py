# -*- coding: utf-8 -*-
"""
Retry and Failure Recovery module for Delivery Status Synchronization Service.
Implements exponential backoff with jitter and Dead-Letter Queue (DLQ) routing.
"""

import random
import time
from typing import Any, Callable, Dict, Optional
import frappe


class RetryExceededError(Exception):
    """Raised when an operation fails after exhausting all retry attempts."""
    pass


def execute_with_retry(
    fn: Callable[[], Any],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
    on_retry: Optional[Callable[[int, Exception], None]] = None,
) -> Any:
    """Execute a callable with exponential backoff and jitter."""
    attempt = 0
    while True:
        try:
            return fn()
        except Exception as e:
            attempt += 1
            if attempt > max_retries:
                raise RetryExceededError(f"Failed after {max_retries} attempts: {e}") from e

            delay = min(base_delay * (2 ** (attempt - 1)), max_delay)
            if jitter:
                delay = delay * (0.5 + random.random())

            if on_retry:
                try:
                    on_retry(attempt, e)
                except Exception:
                    pass

            time.sleep(delay)


def route_to_dlq(payload: Dict[str, Any], reason: str, exc: Optional[Exception] = None) -> None:
    """Route unresolvable status events to Redis DLQ with audit logging."""
    try:
        frappe.logger("tap_buddy_delivery_sync").error(
            f"[DLQ ROUTING] Reason: {reason} | Error: {exc} | Payload Keys: {list(payload.keys())}"
        )
    except Exception:
        pass

    try:
        from tap_buddy.services.redis_utils import get_redis_conn, PREFIX
        conn = get_redis_conn()
        envelope = {
            "payload": payload,
            "reason": reason,
            "error": str(exc) if exc else None,
            "failed_at": frappe.utils.now_datetime().isoformat(),
        }
        conn.lpush(f"{PREFIX}queue:delivery_sync_dlq", frappe.as_json(envelope))
    except Exception as e:
        try:
            frappe.logger("tap_buddy_delivery_sync").critical(
                f"[CRITICAL DLQ WRITE FAILURE] Could not write payload to Redis DLQ: {e}"
            )
        except Exception:
            pass
