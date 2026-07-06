"""
tap_buddy/api/poll_response.py

Task E-02: Poll Ingestion Webhook Receiver

Accepts HTTP POST from a Glific "Call Webhook" node after an educator submits
a WhatsApp poll or survey. Records the response in the ``TAP Poll Response``
DocType as an immutable audit record.

Design Decisions
----------------
* **Secret validation**: The payload must include a ``secret`` field whose value
  matches the ``webhook_secret`` stored in ``TAP Buddy Settings``. This is
  consistent with the project-wide pattern used in ``glific_bq_webhook.py``.

* **Future hardening (E-02 approval, 2026-07-06)**: If Glific adds support for
  request signing, migrate from shared-secret payload validation to HMAC
  signature verification (e.g. ``X-Glific-Signature: sha256=<hmac>`` header).
  This provides stronger payload authenticity guarantees by binding the signature
  to the raw request body rather than a value inside the JSON.  The helper
  ``_validate_signature()`` in ``tap_buddy/api/webhook.py`` can be reused.
  Treat as a future enhancement — payload-secret is the current project standard.

* **Idempotency**: Glific may retry webhook delivery on network failures. If a
  document with the same ``response_id`` already exists, the handler returns
  ``{"success": true, "already_processed": true}`` without creating a duplicate.
  The ``response_id`` field on the DocType is marked ``unique=1`` at the schema
  layer as a second-layer guarantee.

* **Immutability**: Documents are inserted with ``ignore_permissions=True`` but
  the DocType schema sets ``write=0`` for all roles — records cannot be mutated
  via the Frappe UI after ingestion.

* **Required fields**: ``response_id``, ``phone_number``, and ``selected_option``
  are the minimum fields required for a meaningful audit record. All other fields
  (``flow_id``, ``school_code``, ``poll_question``) are accepted when present but
  are not required so that future Glific flow revisions with fewer fields do not
  break the ingestion pipeline.

* **Test seam**: The business logic lives in ``_handle_poll_response(payload)`` so
  that unit tests can call it directly without navigating the ``@frappe.whitelist``
  decorator wrapper.

Endpoint
--------
POST /api/method/tap_buddy.api.poll_response.handle

Expected Payload (JSON)
-----------------------
{
    "secret": "<webhook_secret>",
    "response_id": "<unique response UUID from Glific>",
    "flow_id": "<glific flow id>",
    "phone_number": "<E.164 phone number without +>",
    "school_code": "<UDISE school code>",
    "poll_question": "<full question text>",
    "selected_option": "<option label chosen by educator>",
    "submitted_at": "<ISO-8601 datetime string, optional>"
}

Successful Response (HTTP 200)
------------------------------
{"success": true}                               -- first delivery
{"success": true, "already_processed": true}    -- duplicate delivery

Error Responses
---------------
400  Missing JSON payload / malformed JSON / missing required fields
401  Invalid or missing webhook secret
500  Unexpected server error
"""
import json
from datetime import datetime, timezone

import frappe


# ---------------------------------------------------------------------------
# Required fields that MUST be present in every valid payload
# ---------------------------------------------------------------------------
REQUIRED_FIELDS = ("response_id", "phone_number", "selected_option")


@frappe.whitelist(allow_guest=True)
def handle():
    """Poll ingestion webhook handler — Frappe entry point.

    Reads the raw request body and delegates all logic to
    ``_handle_poll_response`` so that unit tests can exercise the business
    logic without the ``@frappe.whitelist`` decorator wrapper.
    """
    frappe.local.response.content_type = "application/json"
    logger = frappe.logger("tap_buddy_poll")

    raw_body = frappe.request.get_data(as_text=True) if hasattr(frappe, "request") else None
    if not raw_body:
        frappe.local.response.http_status_code = 400
        return {"success": False, "error": "Missing JSON payload."}

    try:
        payload = json.loads(raw_body)
    except (json.JSONDecodeError, ValueError):
        frappe.local.response.http_status_code = 400
        return {"success": False, "error": "Malformed JSON payload."}

    if not isinstance(payload, dict):
        frappe.local.response.http_status_code = 400
        return {"success": False, "error": "Payload must be a JSON object."}

    return _handle_poll_response(payload)


def _handle_poll_response(payload: dict) -> dict:
    """Core business logic for poll response ingestion.

    This function is separated from the decorated ``handle()`` entry point so
    that unit tests can invoke it directly with a pre-built payload dict
    without needing to navigate the ``@frappe.whitelist`` decorator.

    Args:
        payload: Parsed JSON dict from the webhook body.

    Returns:
        Response dict that Frappe will serialise to JSON.
        Side-effects: sets ``frappe.local.response.http_status_code`` on errors.
    """
    logger = frappe.logger("tap_buddy_poll")

    # ------------------------------------------------------------------
    # 1. Authenticate: compare secret against TAP Buddy Settings
    # ------------------------------------------------------------------
    try:
        settings = frappe.get_single("TAP Buddy Settings")
        expected_secret = (
            settings.get_password("webhook_secret")
            if hasattr(settings, "get_password")
            else settings.webhook_secret
        )
    except Exception as e:
        logger.error(f"[PollResponse] Failed to load TAP Buddy Settings: {e}")
        frappe.local.response.http_status_code = 500
        return {"success": False, "error": "Server configuration error."}

    provided_secret = payload.get("secret")
    if not provided_secret or not expected_secret or provided_secret != expected_secret:
        logger.warning("[PollResponse] Unauthorized: invalid or missing webhook secret.")
        frappe.local.response.http_status_code = 401
        return {"success": False, "error": "Unauthorized."}

    # ------------------------------------------------------------------
    # 2. Validate required fields
    # ------------------------------------------------------------------
    missing = [f for f in REQUIRED_FIELDS if not payload.get(f)]
    if missing:
        logger.warning(f"[PollResponse] Missing required fields: {missing}")
        frappe.local.response.http_status_code = 400
        return {"success": False, "error": f"Missing required fields: {missing}"}

    response_id = payload["response_id"]

    # ------------------------------------------------------------------
    # 3. Idempotency check: skip if already processed
    # ------------------------------------------------------------------
    if frappe.db.exists("TAP Poll Response", {"response_id": response_id}):
        logger.info(f"[PollResponse] Duplicate delivery for response_id={response_id}. Skipping.")
        return {"success": True, "already_processed": True}

    # ------------------------------------------------------------------
    # 4. Build and insert the document
    # ------------------------------------------------------------------
    submitted_at = payload.get("submitted_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    try:
        doc = frappe.new_doc("TAP Poll Response")
        doc.response_id = response_id
        doc.flow_id = payload.get("flow_id") or ""
        doc.phone_number = payload["phone_number"]
        doc.school_code = payload.get("school_code") or ""
        doc.poll_question = payload.get("poll_question") or ""
        doc.selected_option = payload["selected_option"]
        doc.submitted_at = submitted_at
        doc.insert(ignore_permissions=True)

        logger.info(f"[PollResponse] Inserted TAP Poll Response: {doc.name} (response_id={response_id})")
        return {"success": True}

    except Exception as e:
        logger.error(f"[PollResponse] Failed to insert TAP Poll Response: {e}")
        frappe.local.response.http_status_code = 500
        return {"success": False, "error": "Failed to record poll response. Please retry."}
