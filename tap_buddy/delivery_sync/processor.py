# -*- coding: utf-8 -*-
"""
Status Processing Engine for Delivery Status Synchronization Service.
Maps provider_message_id to internal DocTypes and performs bulk idempotent updates.
"""

from datetime import datetime
from typing import List
import frappe

from tap_buddy.delivery_sync.models import DeliveryStatusEvent, SyncBatchResult
from tap_buddy.delivery_sync.metrics import DeliverySyncMetrics
from tap_buddy.delivery_sync.retry import route_to_dlq


STATUS_PRECEDENCE = {
    "sent": 1,
    "delivered": 2,
    "read": 3,
    "failed": 4,
}


class DeliveryStatusProcessor:
    """Processes normalized status events and reconciles internal TAP Buddy records."""

    @classmethod
    def process_batch(cls, events: List[DeliveryStatusEvent], batch_id: str) -> SyncBatchResult:
        result = SyncBatchResult(batch_id=batch_id, start_time=datetime.utcnow())
        if not events:
            result.end_time = datetime.utcnow()
            return result

        DeliverySyncMetrics.increment_counter("events_received", len(events))

        # Deduplicate events in batch by selecting highest precedence status per provider_message_id
        deduped = {}
        for ev in events:
            bsp_id = ev.provider_message_id
            if not bsp_id:
                continue
            if bsp_id not in deduped:
                deduped[bsp_id] = ev
            else:
                curr_prec = STATUS_PRECEDENCE.get(deduped[bsp_id].status, 0)
                new_prec = STATUS_PRECEDENCE.get(ev.status, 0)
                if new_prec > curr_prec:
                    deduped[bsp_id] = ev

        for bsp_id, ev in deduped.items():
            try:
                updated_log = cls._update_message_log(ev)
                updated_recip = cls._update_campaign_recipient(ev)
                
                if updated_log:
                    result.updated_logs += 1
                    DeliverySyncMetrics.increment_counter("message_logs_updated", 1)
                if updated_recip:
                    result.updated_recipients += 1
                    DeliverySyncMetrics.increment_counter("recipients_updated", 1)

                result.processed_count += 1
                DeliverySyncMetrics.increment_counter("events_processed", 1)
            except Exception as e:
                result.errors.append(f"{bsp_id}: {str(e)}")
                result.dlq_count += 1
                DeliverySyncMetrics.increment_counter("events_failed", 1)
                route_to_dlq(ev.raw_payload, f"Reconciliation Error: {e}", exc=e)

        if result.updated_recipients > 0 or result.updated_logs > 0:
            try:
                frappe.db.commit()
            except Exception:
                pass

        result.end_time = datetime.utcnow()
        DeliverySyncMetrics.record_latency("process_batch", result.duration_ms)
        return result

    @staticmethod
    def _update_message_log(event: DeliveryStatusEvent) -> bool:
        """Update Message Log record if status precedence is higher."""
        logs = frappe.db.sql(
            """
            SELECT name, status
            FROM `tabMessage Log`
            WHERE provider_message_id = %s
            LIMIT 1
            """,
            (event.provider_message_id,),
            as_dict=True,
        )
        if not logs:
            return False

        log_name = logs[0].name
        current_status = str(logs[0].status or "").lower()
        
        curr_prec = STATUS_PRECEDENCE.get(current_status, 0)
        new_prec = STATUS_PRECEDENCE.get(event.status, 0)

        if new_prec <= curr_prec and current_status != "sent":
            return False

        update_values = {"status": event.status}
        ts_str = event.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        if event.status == "delivered":
            update_values["delivered_at"] = ts_str
        elif event.status == "read":
            update_values["read_at"] = ts_str
        elif event.status == "failed":
            update_values["error_message"] = event.error_reason or "Provider delivery failure"

        frappe.db.set_value("Message Log", log_name, update_values, update_modified=True)
        return True

    @staticmethod
    def _update_campaign_recipient(event: DeliveryStatusEvent) -> bool:
        """Update Campaign Recipient status matching provider_message_id."""
        recips = frappe.db.sql(
            """
            SELECT name, status, parent
            FROM `tabCampaign Recipient`
            WHERE provider_message_id = %s
            LIMIT 1
            """,
            (event.provider_message_id,),
            as_dict=True,
        )
        if not recips:
            return False

        recip_name = recips[0].name
        current_status = str(recips[0].status or "").lower()

        curr_prec = STATUS_PRECEDENCE.get(current_status, 0)
        new_prec = STATUS_PRECEDENCE.get(event.status, 0)

        if new_prec <= curr_prec and current_status != "sent":
            return False

        capitalized_status = event.status.capitalize()
        frappe.db.set_value("Campaign Recipient", recip_name, "status", capitalized_status, update_modified=True)
        return True
