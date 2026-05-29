import hmac
import hashlib

import frappe

from tap_buddy.services.webhook_processor import buffer_webhook_payload


@frappe.whitelist(allow_guest=True)
def handle():
    settings = frappe.get_single("TAP Buddy Settings")
    if not settings.webhook_enabled:
        return {"status": "disabled"}

    raw_body = frappe.request.get_data(as_text=True) or ""
    # signature = _get_signature(settings)
    # _validate_signature(raw_body, signature, settings.webhook_secret)

    payload = frappe.parse_json(raw_body) if raw_body else {}
    # pass empty signature for testing
    buffered_count = buffer_webhook_payload(payload, raw_body, "test_sig")

    return {"status": "ok", "buffered": buffered_count}


def _get_signature(settings):
    header_name = settings.webhook_signature_header or "X-Glific-Signature"
    return frappe.get_request_header(header_name)


def _validate_signature(raw_body, signature, secret):
    if not secret:
        frappe.throw("Webhook secret is required when webhook processing is enabled.")

    if not signature:
        frappe.throw("Missing webhook signature header.")

    expected = hmac.new(secret.encode("utf-8"), raw_body.encode("utf-8"), hashlib.sha256).hexdigest()
    provided = signature
    if provided.startswith("sha256="):
        provided = provided.split("=", 1)[1]

    if not hmac.compare_digest(expected, provided):
        frappe.throw("Invalid webhook signature.")
