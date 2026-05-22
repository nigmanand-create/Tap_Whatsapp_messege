import hmac
import hashlib

import frappe

from tap_buddy.services.lms_ingestion import enqueue_lms_events


@frappe.whitelist(allow_guest=True)
def handle():
    settings = frappe.get_single("LMS Integration Settings")
    if not settings.enabled:
        return {"status": "disabled"}

    raw_body = frappe.request.get_data(as_text=True) or ""
    signature = _get_signature(settings)
    _validate_signature(raw_body, signature, settings.webhook_secret)

    payload = frappe.parse_json(raw_body) if raw_body else {}
    event_names = enqueue_lms_events(payload, raw_body, signature)

    return {"status": "ok", "events": len(event_names)}


def _get_signature(settings):
    header_name = settings.webhook_signature_header or "X-LMS-Signature"
    return frappe.get_request_header(header_name)


def _validate_signature(raw_body, signature, secret):
    if not secret:
        frappe.throw("Webhook secret is required when LMS webhook processing is enabled.")

    if not signature:
        frappe.throw("Missing LMS webhook signature header.")

    expected = hmac.new(secret.encode("utf-8"), raw_body.encode("utf-8"), hashlib.sha256).hexdigest()
    provided = signature
    if provided.startswith("sha256="):
        provided = provided.split("=", 1)[1]

    if not hmac.compare_digest(expected, provided):
        frappe.throw("Invalid LMS webhook signature.")
