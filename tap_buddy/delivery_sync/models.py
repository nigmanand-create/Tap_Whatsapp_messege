# -*- coding: utf-8 -*-
"""
Models for the Delivery Status Synchronization Service.
Defines typed data structures for status events, reconciliation results, and worker heartbeat.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class DeliveryStatusEvent:
    """Represents a normalized delivery status update from Glific/BSP."""
    provider_message_id: str
    status: str  # 'sent', 'delivered', 'read', 'failed', 'error'
    timestamp: datetime
    raw_payload: Dict[str, Any] = field(default_factory=dict)
    contact_phone: Optional[str] = None
    error_reason: Optional[str] = None

    @classmethod
    def from_glific_graphql(cls, data: Dict[str, Any]) -> "DeliveryStatusEvent":
        """Parse a GraphQL waMessage object into a DeliveryStatusEvent."""
        bsp_id = str(data.get("bspId") or data.get("bspMessageId") or data.get("bsp_message_id") or data.get("bsp_id") or data.get("id") or "").strip()
        raw_status = str(data.get("bspStatus") or data.get("bsp_status") or data.get("status") or "").lower()
        
        status_map = {
            "sent": "sent",
            "enqueued": "sent",
            "delivered": "delivered",
            "read": "read",
            "seen": "read",
            "error": "failed",
            "failed": "failed",
            "undelivered": "failed",
        }
        normalized_status = status_map.get(raw_status, "failed" if "error" in raw_status else raw_status)

        ts_raw = data.get("updatedAt") or data.get("updated_at") or data.get("insertedAt")
        ts = datetime.utcnow()
        if ts_raw:
            try:
                if isinstance(ts_raw, str):
                    ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                pass

        contact = data.get("contact") or {}
        phone = contact.get("phone") if isinstance(contact, dict) else None

        errors = data.get("errors")
        err_msg = str(errors) if errors else None

        return cls(
            provider_message_id=bsp_id,
            status=normalized_status,
            timestamp=ts,
            raw_payload=data,
            contact_phone=phone,
            error_reason=err_msg,
        )


@dataclass
class SyncBatchResult:
    """Tracks metrics and outcomes of processing a batch of status events."""
    batch_id: str
    processed_count: int = 0
    updated_logs: int = 0
    updated_recipients: int = 0
    dlq_count: int = 0
    errors: List[str] = field(default_factory=list)
    start_time: datetime = field(default_factory=datetime.utcnow)
    end_time: Optional[datetime] = None

    @property
    def duration_ms(self) -> float:
        if not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds() * 1000.0


@dataclass
class WorkerState:
    """Represents the real-time operational state of the delivery sync worker."""
    worker_id: str
    status: str  # 'IDLE', 'RUNNING', 'PAUSED', 'ERROR', 'STOPPED'
    last_heartbeat: datetime
    consecutive_failures: int = 0
    total_events_synced: int = 0
    last_error: Optional[str] = None
