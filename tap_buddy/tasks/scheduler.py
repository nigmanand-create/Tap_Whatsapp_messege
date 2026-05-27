from datetime import timedelta
from typing import Any, cast
import frappe
from frappe.utils import get_datetime, get_time, now_datetime

from tap_buddy.services.glific_client import GlificAPIError, GlificTerminalError, GlificClient
from tap_buddy.services.recipients import build_campaign_recipients, get_recipient_context
from tap_buddy.services.template_renderer import render_template
from tap_buddy.services.webhook_processor import process_pending_events
from tap_buddy.services.glific_sync import sync_glific
from tap_buddy.services.lms_ingestion import process_pending_lms_events as lms_process_pending_events
from tap_buddy.services.db_utils import get_pending_recipients_for_update, get_failed_recipients_for_update, mark_recipients_processing
from tap_buddy.services.redis_utils import consume_token_bucket

from tap_buddy.utils.constants import (
    ATTEMPT_STATUS_FAILED,
    ATTEMPT_STATUS_QUEUED,
    ATTEMPT_STATUS_SENT,
    REC_STATUS_FAILED,
    REC_STATUS_PENDING,
    REC_STATUS_QUEUED,
    REC_STATUS_PROCESSING,
    REC_STATUS_SENT,
    STATUS_FAILED,
    STATUS_COMPLETED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    STATUS_SCHEDULED,
    STATUS_SENT,
    is_active_status,
    is_terminal_status,
)
from tap_buddy.utils.phone import normalize_phone_number


def dispatch_campaign(campaign_name):
    """
    Background job to process and send messages for a TAP Campaign.
    Concurrency safe: Uses FOR UPDATE SKIP LOCKED batch claiming.
    """
    campaign = cast(Any, frappe.get_doc("TAP Campaign", campaign_name))
    if campaign.status not in (STATUS_SCHEDULED, STATUS_QUEUED, STATUS_RUNNING, STATUS_SENT):
        return

    if campaign.send_date:
        send_dt = get_datetime(campaign.send_date)
        if send_dt and send_dt > now_datetime():
            return

    settings = cast(Any, frappe.get_single("TAP Buddy Settings"))
    if not _is_within_dispatch_window(settings):
        return

    if campaign.status in (STATUS_SCHEDULED, STATUS_QUEUED):
        frappe.db.set_value("TAP Campaign", campaign.name, "status", STATUS_RUNNING)

    build_campaign_recipients(campaign.name)

    batch_size = _get_batch_size(settings)
    rate_limit = settings.rate_limit or batch_size

    # 1. Atomic Claiming (DB Level Lock)
    claimed_names = get_pending_recipients_for_update(campaign.name, limit=batch_size)
    if not claimed_names:
        return
        
    # 2. Mark Processing
    mark_recipients_processing(claimed_names)
    frappe.db.commit() # Commit the lock release and status update

    # 3. Fetch full context for claimed rows
    recipients = frappe.get_all(
        "Campaign Recipient",
        filters={"name": ["in", claimed_names]},
        fields=["name", "school", "retry_count", "campaign"]
    )

    client = GlificClient()

    for recipient in recipients:
        # 4. Atomic Rate Limiting (Redis Token Bucket)
        if not consume_token_bucket("dispatch_limit", limit=rate_limit, window_seconds=60):
            # Exit early. The stale processing sweeper will safely revert these back to Pending later.
            break
            
        _dispatch_recipient(client, campaign, recipient)


def retry_failed_messages():
    """
    Scheduled job to retry sending messages that failed (transiently).
    Concurrency safe.
    """
    settings = cast(Any, frappe.get_single("TAP Buddy Settings"))
    if not _is_within_dispatch_window(settings):
        return

    _sweep_stale_processing_recipients()

    max_retries = settings.retry_count or 0
    batch_size = _get_batch_size(settings)
    rate_limit = settings.rate_limit or batch_size

    active_campaigns = frappe.get_all(
        "TAP Campaign",
        filters={"status": ["in", [STATUS_SCHEDULED, STATUS_QUEUED, STATUS_RUNNING]]},
        fields=["name"],
    )
    campaign_names = [c.name for c in active_campaigns]
    if not campaign_names:
        return

    # 1. Atomic Claiming (DB Level Lock)
    claimed_names = get_failed_recipients_for_update(campaign_names, limit=batch_size, max_retries=max_retries)
    if not claimed_names:
        return

    # 2. Mark Processing
    mark_recipients_processing(claimed_names)
    frappe.db.commit()

    recipients = frappe.get_all(
        "Campaign Recipient",
        filters={"name": ["in", claimed_names]},
        fields=["name", "school", "retry_count", "campaign"]
    )
    
    client = GlificClient()

    for recipient in recipients:
        if not consume_token_bucket("dispatch_limit", limit=rate_limit, window_seconds=60):
            break
            
        campaign = frappe.get_doc("TAP Campaign", recipient.campaign)
        if not is_active_status(campaign.status):
            continue
            
        _dispatch_recipient(client, campaign, recipient)


def sweep_stale_campaigns():
    """
    Scheduled job to clean up or mark campaigns as stale.
    """
    cutoff = now_datetime() - timedelta(days=1)
    campaigns = frappe.get_all(
        "TAP Campaign",
        filters={"status": ["in", [STATUS_SCHEDULED, STATUS_QUEUED, STATUS_RUNNING]], "send_date": ["<", cutoff]},
        fields=["name", "status"],
    )

    for campaign in campaigns:
        pending = frappe.db.count(
            "Campaign Recipient",
            filters={
                "campaign": campaign.name,
                "status": ["in", [REC_STATUS_PENDING, REC_STATUS_QUEUED, REC_STATUS_FAILED]],
            },
        )
        if pending == 0:
            frappe.db.set_value("TAP Campaign", campaign.name, "status", STATUS_FAILED)


def sync_campaign_counts():
    """
    Scheduled job to sync delivery/read counts for campaigns.
    """
    campaigns = frappe.get_all(
        "TAP Campaign",
        filters={"status": ["in", [STATUS_SCHEDULED, STATUS_QUEUED, STATUS_RUNNING, STATUS_SENT, STATUS_FAILED]]},
        fields=["name", "status"],
    )

    for campaign in campaigns:
        total = frappe.db.count("Campaign Recipient", filters={"campaign": campaign.name})
        sent = frappe.db.count(
            "Campaign Recipient",
            filters={"campaign": campaign.name, "status": ["in", [REC_STATUS_SENT]]},
        )
        success = frappe.db.count(
            "Campaign Recipient",
            filters={"campaign": campaign.name, "status": ["in", [REC_STATUS_SENT, "Delivered", "Read"]]},
        )
        delivered = frappe.db.count(
            "Campaign Recipient",
            filters={"campaign": campaign.name, "status": ["in", ["Delivered", "Read"]]},
        )
        failed = frappe.db.count(
            "Campaign Recipient",
            filters={"campaign": campaign.name, "status": REC_STATUS_FAILED},
        )
        terminal = frappe.db.count(
            "Campaign Recipient",
            filters={
                "campaign": campaign.name,
                "status": ["in", [REC_STATUS_SENT, "Delivered", "Read", REC_STATUS_FAILED]],
            },
        )

        frappe.db.set_value(
            "TAP Campaign",
            campaign.name,
            {
                "total_recipients": total,
                "sent_count": sent,
                "delivered_count": delivered,
                "failed_count": failed,
            },
        )

        if total and terminal == total and is_active_status(campaign.status):
            if success > 0:
                frappe.db.set_value("TAP Campaign", campaign.name, "status", STATUS_COMPLETED)
            else:
                frappe.db.set_value("TAP Campaign", campaign.name, "status", STATUS_FAILED)


def process_pending_webhook_events():
    """
    Scheduled job to process pending webhook events.
    """
    process_pending_events()


def process_pending_lms_events():
    """
    Scheduled job to process pending LMS events.
    """
    lms_process_pending_events()


def process_glific_sync():
    """
    Scheduled job to sync contacts/groups to Glific.
    """
    sync_glific()


def _dispatch_recipient(client, campaign, recipient):
    school = frappe.get_doc("School", recipient.school)
    phone = normalize_phone_number(school.whatsapp_number)
    
    if not phone:
        _mark_failed(recipient, "Missing WhatsApp number", increment_retry=False, terminal=True)
        return

    message = _render_message(campaign, school)
    if not message:
        _mark_failed(recipient, "Empty message after rendering", increment_retry=False, terminal=True)
        return

    # Stable idempotency key: unique to the recipient intent, ignores retry counts.
    idempotency_key = f"tap_{campaign.name}_{recipient.name}"
    
    # Save the key back to the recipient doc for audit
    frappe.db.set_value("Campaign Recipient", recipient.name, "idempotency_key", idempotency_key)

    attempt_name = _create_dispatch_attempt(campaign, recipient, phone, message, idempotency_key)

    sent_at = now_datetime()
    try:
        response = client.send_message(phone, message, idempotency_key=idempotency_key)
        provider_id = _extract_provider_message_id(response)
        
        _update_dispatch_attempt_success(attempt_name, response, provider_id)
        _create_message_log(campaign, school, phone, message, response, provider_id, REC_STATUS_SENT, sent_at)
        
        frappe.db.set_value(
            "Campaign Recipient",
            recipient.name,
            {"status": REC_STATUS_SENT, "sent_time": sent_at, "failure_reason": None},
        )
        
    except GlificTerminalError as exc:
        _mark_failed(recipient, str(exc), attempt_name, terminal=True)
        _create_message_log(campaign, school, phone, message, {"error": str(exc)}, None, REC_STATUS_FAILED, None)
    except GlificAPIError as exc:
        _mark_failed(recipient, str(exc), attempt_name, terminal=False)
        _create_message_log(campaign, school, phone, message, {"error": str(exc)}, None, REC_STATUS_FAILED, None)
    except Exception as exc:
        frappe.log_error(title="Dispatch Error", message=frappe.get_traceback())
        _mark_failed(recipient, str(exc), attempt_name, terminal=False)
        _create_message_log(campaign, school, phone, message, {"error": str(exc)}, None, REC_STATUS_FAILED, None)
    
    frappe.db.commit()


def _render_message(campaign, school):
    template_text = _get_template_text(campaign)
    context = get_recipient_context(school.name)
    return render_template(template_text, context)


def _get_template_text(campaign):
    if campaign.message_template:
        return campaign.message_template
    if campaign.template:
        return frappe.get_value("WhatsApp Template", campaign.template, "message") or frappe.get_value(
            "WhatsApp Template", campaign.template, "message_body"
        )
    return ""


def _create_message_log(campaign, school, phone, message, response, provider_id, status, sent_at):
    log = frappe.new_doc("Message Log")
    log.campaign = campaign.name
    log.school = school.name
    log.phone_number = phone
    log.message = message
    log.status = status
    log.api_response = frappe.as_json(response)
    log.provider_message_id = provider_id
    log.sent_at = sent_at
    log.insert(ignore_permissions=True)


def _create_dispatch_attempt(campaign, recipient, phone, message, idempotency_key):
    attempt = frappe.new_doc("Dispatch Attempt")
    attempt.campaign = campaign.name
    attempt.recipient = recipient.name
    attempt.school = recipient.school
    attempt.phone_number = phone
    attempt.message = message
    attempt.status = ATTEMPT_STATUS_QUEUED
    attempt.attempt_time = now_datetime()
    attempt.idempotency_key = idempotency_key
    attempt.retry_count = recipient.retry_count or 0
    attempt.insert(ignore_permissions=True)
    return attempt.name


def _update_dispatch_attempt_success(attempt_name, response, provider_id):
    frappe.db.set_value(
        "Dispatch Attempt",
        attempt_name,
        {
            "status": ATTEMPT_STATUS_SENT,
            "api_response": frappe.as_json(response),
            "provider_message_id": provider_id,
        },
    )


def _mark_failed(recipient, reason, attempt_name=None, increment_retry=True, terminal=False):
    current_retry = recipient.retry_count or 0
    next_retry = current_retry + 1 if increment_retry else current_retry
    
    updates = {
        "status": REC_STATUS_FAILED,
        "failure_reason": reason,
        "retry_count": next_retry,
    }
    
    if terminal:
        updates["terminal_failure"] = 1

    frappe.db.set_value("Campaign Recipient", recipient.name, updates)
    
    if attempt_name:
        frappe.db.set_value(
            "Dispatch Attempt",
            attempt_name,
            {
                "status": ATTEMPT_STATUS_FAILED,
                "error_message": reason,
                "terminal_failure": 1 if terminal else 0
            },
        )


def _extract_provider_message_id(response):
    if not response:
        return None
    if isinstance(response, dict):
        return response.get("id") or response.get("message_id") or response.get("messageId")
    return None


def _get_batch_size(settings):
    batch_size = settings.batch_size or 50
    rate_limit = settings.rate_limit or batch_size
    return min(batch_size, rate_limit)


def _is_within_dispatch_window(settings):
    start_time = get_time(settings.dispatch_start_hour)
    end_time = get_time(settings.dispatch_end_hour)
    now_time = now_datetime().time()

    if not start_time or not end_time:
        return True

    if start_time <= end_time:
        return start_time <= now_time <= end_time

    return now_time >= start_time or now_time <= end_time


def _sweep_stale_processing_recipients():
    """
    Mark recipients stuck in 'Processing' for too long as 'Pending'.
    This safely recovers rows abandoned by crashed workers without wasting retry counts.
    """
    cutoff = now_datetime() - timedelta(minutes=45)
    stuck = frappe.get_all(
        "Campaign Recipient",
        filters={"status": REC_STATUS_PROCESSING, "modified": ["<", cutoff]},
        fields=["name", "retry_count", "campaign"]
    )
    
    if not stuck:
        return
        
    stuck_names = [s.name for s in stuck]
    
    # We revert them to Pending. The dispatcher will naturally pick them up again.
    if frappe.db.db_type == "postgres":
        frappe.db.sql(f"""
            UPDATE "tabCampaign Recipient"
            SET status = 'Pending'
            WHERE name IN ({", ".join(["%s"] * len(stuck_names))})
        """, stuck_names)
    else:
        frappe.db.sql(f"""
            UPDATE `tabCampaign Recipient`
            SET status = 'Pending'
            WHERE name IN ({", ".join(["%s"] * len(stuck_names))})
        """, stuck_names)
    
    frappe.db.commit()
    frappe.logger("tap_buddy_dispatch").warning(f"Reverted {len(stuck_names)} stale Processing recipients to Pending.")
