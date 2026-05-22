from datetime import timedelta
from typing import Any, cast
import frappe
from frappe.utils import get_datetime, get_time, now_datetime

from tap_buddy.services.glific_client import GlificAPIError, GlificClient
from tap_buddy.services.recipients import build_campaign_recipients, get_recipient_context
from tap_buddy.services.template_renderer import render_template
from tap_buddy.services.webhook_processor import process_pending_events
from tap_buddy.services.glific_sync import sync_glific
from tap_buddy.services.lms_ingestion import process_pending_lms_events as lms_process_pending_events
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
    """
    campaign = cast(Any, frappe.get_doc("TAP Campaign", campaign_name))
    if campaign.status not in (STATUS_SCHEDULED, STATUS_QUEUED, STATUS_RUNNING, STATUS_SENT):
        return

    if campaign.send_date and get_datetime(campaign.send_date) > now_datetime():
        return

    settings = cast(Any, frappe.get_single("TAP Buddy Settings"))
    if not _is_within_dispatch_window(settings):
        return

    if campaign.status in (STATUS_SCHEDULED, STATUS_QUEUED):
        frappe.db.set_value("TAP Campaign", campaign.name, "status", STATUS_RUNNING)

    build_campaign_recipients(campaign.name)

    batch_size = _get_batch_size(settings)
    recipients = cast(Any, frappe.get_all(
        "Campaign Recipient",
        filters={"campaign": campaign.name, "status": REC_STATUS_PENDING},
        fields=["name", "school", "retry_count"],
        order_by="creation asc",
        limit=batch_size,
    ))

    for recipient in recipients:
        if not _consume_rate_limit(settings):
            break
        _dispatch_recipient(campaign, recipient)


def retry_failed_messages():
    """
    Scheduled job to retry sending messages that failed.
    """
    settings = cast(Any, frappe.get_single("TAP Buddy Settings"))
    if not _is_within_dispatch_window(settings):
        return

    _sweep_stale_processing_recipients()

    max_retries = settings.retry_count or 0
    batch_size = _get_batch_size(settings)

    # Restrict to recipients whose campaigns are currently active to avoid
    # scanning large numbers of failed recipients from inactive campaigns.
    active_campaigns = cast(Any, frappe.get_all(
        "TAP Campaign",
        filters={"status": ["in", [STATUS_SCHEDULED, STATUS_QUEUED, STATUS_RUNNING]]},
        fields=["name"],
    ))
    campaign_names = [c.name for c in active_campaigns]
    if not campaign_names:
        return

    candidates = cast(Any, frappe.get_all(
        "Campaign Recipient",
        filters={
            "status": REC_STATUS_FAILED,
            "retry_count": ["<", max_retries],
            "campaign": ["in", campaign_names],
        },
        fields=["name", "school", "campaign", "retry_count"],
        order_by="modified asc",
        limit=batch_size,
    ))

    for recipient in candidates:
        if not _consume_rate_limit(settings):
            break
        campaign = cast(Any, frappe.get_doc("TAP Campaign", recipient.campaign))
        if not is_active_status(campaign.status):
            continue
        _dispatch_recipient(campaign, recipient)


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


def _dispatch_recipient(campaign, recipient):
    if not _claim_recipient(recipient.name):
        return

    frappe.db.set_value("Campaign Recipient", recipient.name, "status", REC_STATUS_PROCESSING)
    frappe.db.commit()

    school = cast(Any, frappe.get_doc("School", recipient.school))
    phone = normalize_phone_number(school.whatsapp_number)
    if not phone:
        _mark_failed(recipient, "Missing WhatsApp number", increment_retry=False)
        return

    message = _render_message(campaign, school)
    if not message:
        _mark_failed(recipient, "Empty message after rendering", increment_retry=False)
        return

    idempotency_key = f"{campaign.name}:{recipient.name}:{(recipient.retry_count or 0) + 1}"
    attempt_name = _create_dispatch_attempt(campaign, recipient, phone, message, idempotency_key)

    client = GlificClient()
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
    except GlificAPIError as exc:
        _mark_failed(recipient, str(exc), attempt_name)
        _create_message_log(campaign, school, phone, message, {"error": str(exc)}, None, REC_STATUS_FAILED, None)
    except Exception as exc:
        frappe.log_error(title="Dispatch Error", message=frappe.get_traceback())
        _mark_failed(recipient, str(exc), attempt_name)
        _create_message_log(campaign, school, phone, message, {"error": str(exc)}, None, REC_STATUS_FAILED, None)


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
    log = cast(Any, frappe.new_doc("Message Log"))
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
    attempt = cast(Any, frappe.new_doc("Dispatch Attempt"))
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


def _mark_failed(recipient, reason, attempt_name=None, increment_retry=True):
    current_retry = recipient.retry_count or 0
    next_retry = current_retry + 1 if increment_retry else current_retry
    frappe.db.set_value(
        "Campaign Recipient",
        recipient.name,
        {
            "status": REC_STATUS_FAILED,
            "failure_reason": reason,
            "retry_count": next_retry,
        },
    )
    if attempt_name:
        frappe.db.set_value(
            "Dispatch Attempt",
            attempt_name,
            {
                "status": ATTEMPT_STATUS_FAILED,
                "error_message": reason,
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


def _consume_rate_limit(settings, count=1):
    rate_limit = settings.rate_limit or 0
    if not rate_limit:
        return True

    bucket = now_datetime().strftime("%Y%m%d%H%M")
    key = f"tap_buddy:dispatch_rate:{bucket}"
    cache = cast(Any, frappe.cache())  # type: ignore
    current = int(cache.get_value(key) or 0)
    if current + count > rate_limit:
        return False
    cache.set_value(key, current + count, expires_in_sec=70)
    return True


def _claim_recipient(recipient_name):
    if frappe.db.db_type == "postgres":
        updated = frappe.db.sql(
            """
            update "tabCampaign Recipient"
            set status=%s
            where name=%s and status in (%s, %s)
            returning name
            """,
            (REC_STATUS_QUEUED, recipient_name, REC_STATUS_PENDING, REC_STATUS_FAILED),
        )
        return bool(updated)

    frappe.db.sql(
        """
        update `tabCampaign Recipient`
        set status=%s
        where name=%s and status in (%s, %s)
        """,
        (REC_STATUS_QUEUED, recipient_name, REC_STATUS_PENDING, REC_STATUS_FAILED),
    )
    return frappe.db._cursor.rowcount > 0


def _sweep_stale_processing_recipients():
    """
    Mark recipients stuck in 'Processing' for too long as 'Failed' so they can be retried.
    """
    cutoff = now_datetime() - timedelta(minutes=30)
    stuck = cast(Any, frappe.get_all(
        "Campaign Recipient",
        filters={"status": REC_STATUS_PROCESSING, "modified": ["<", cutoff]},
        fields=["name", "retry_count"]
    ))
    for r in stuck:
        _mark_failed(r, "Stuck in Processing state", increment_retry=False)

