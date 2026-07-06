# -*- coding: utf-8 -*-
"""
Orchestration Worker for Delivery Status Synchronization Service.
Coordinates polling, batch processing, and campaign count aggregation.
"""

from datetime import datetime, timedelta
import uuid
import frappe
from typing import Dict, Any

from tap_buddy.delivery_sync.client import GlificSyncClient
from tap_buddy.delivery_sync.processor import DeliveryStatusProcessor
from tap_buddy.delivery_sync.models import WorkerState


class DeliverySyncWorker:
    """Manages scheduled synchronization cycles and lock enforcement."""

    LOCK_KEY = "delivery_sync_worker_lock"
    LAST_SYNC_KEY = "delivery_sync_last_timestamp"

    @classmethod
    def run_sync_cycle(cls, lookback_minutes: int = 15, max_batches: int = 5) -> Dict[str, Any]:
        """Execute one complete synchronization cycle across pending status events."""
        from tap_buddy.services.redis_utils import get_redis_conn, PREFIX
        conn = get_redis_conn()
        lock = conn.lock(f"{PREFIX}{cls.LOCK_KEY}", timeout=120)

        if not lock.acquire(blocking=False):
            return {"status": "SKIPPED", "reason": "Worker lock already acquired by another process"}

        worker_id = f"worker-{uuid.uuid4().hex[:8]}"
        state = WorkerState(worker_id=worker_id, status="RUNNING", last_heartbeat=datetime.utcnow())

        try:
            last_ts_str = conn.get(f"{PREFIX}{cls.LAST_SYNC_KEY}")
            if last_ts_str:
                try:
                    since = datetime.fromisoformat(last_ts_str.decode("utf-8") if isinstance(last_ts_str, bytes) else last_ts_str)
                except Exception:
                    since = datetime.utcnow() - timedelta(minutes=lookback_minutes)
            else:
                since = datetime.utcnow() - timedelta(minutes=lookback_minutes)

            client = GlificSyncClient()
            total_processed = 0
            offset = 0
            batch_limit = 200

            for _ in range(max_batches):
                state.last_heartbeat = datetime.utcnow()
                events = client.fetch_recent_status_updates(since=since, limit=batch_limit, offset=offset)
                if not events:
                    break

                batch_id = f"batch-{uuid.uuid4().hex[:8]}"
                res = DeliveryStatusProcessor.process_batch(events, batch_id=batch_id)
                total_processed += res.processed_count
                offset += batch_limit

                if len(events) < batch_limit:
                    break

            # Trigger campaign count sync to reconcile aggregate counters
            try:
                from tap_buddy.tasks.scheduler import sync_campaign_counts
                sync_campaign_counts()
            except Exception as e:
                frappe.logger("tap_buddy_delivery_sync").warning(f"[SCHEDULER SYNC WARNING] {e}")

            new_last_ts = datetime.utcnow().isoformat()
            conn.set(f"{PREFIX}{cls.LAST_SYNC_KEY}", new_last_ts)

            state.status = "IDLE"
            state.total_events_synced = total_processed
            return {
                "status": "SUCCESS",
                "worker_id": worker_id,
                "total_processed": total_processed,
                "synced_until": new_last_ts,
            }

        except Exception as e:
            state.status = "ERROR"
            state.last_error = str(e)
            frappe.logger("tap_buddy_delivery_sync").error(f"[WORKER CRITICAL FAILURE] {e}")
            return {"status": "ERROR", "worker_id": worker_id, "error": str(e)}
        finally:
            try:
                lock.release()
            except Exception:
                pass


def run_sync_cycle(*args, **kwargs):
    """Module-level wrapper for Frappe scheduler events."""
    return DeliverySyncWorker.run_sync_cycle(*args, **kwargs)
