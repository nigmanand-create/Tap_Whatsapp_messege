"""
glific_template_service.py
==========================
Whitelisted API endpoints for HSM template management:

  1. create_and_push_template(template_name)
     - Creates WhatsApp Template record in Frappe (or uses existing)
     - Pushes it to Glific via createSessionTemplate GraphQL
     - Updates DocType with Glific push status + ID

  2. send_test_message(template_name, phone, p1, p2, p3, p4)
     - Sends a test WhatsApp HSM message to the given phone
     - Uses the approved `pta_meeting_alert_v2` template for immediate
       delivery (new templates take 24-48h for Meta approval)
     - Returns send result with message ID and status

Called from Cypress E2E test and the TAP Buddy desk UI.
"""

import re
import frappe
from frappe.utils import now_datetime

from tap_buddy.services.glific_client import GlificClient, GlificTerminalError, GlificAPIError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _slugify(text: str) -> str:
    """Convert a human label to a valid Glific shortcode (lowercase, underscores)."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s_]", "", text)
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text[:60]  # Glific shortcode length limit


def _detect_params(body: str) -> str:
    """Return comma-separated list of {{N}} placeholders found in body."""
    return ",".join(sorted(set(re.findall(r"\{\{\d+\}\}", body))))


# ---------------------------------------------------------------------------
# API: create_and_push_template
# ---------------------------------------------------------------------------

@frappe.whitelist()
def create_and_push_template(
    template_name: str,
    message: str = "",
    language: str = "English",
    category: str = "UTILITY",
    glific_shortcode: str = "",
    force_push: bool = False,
):
    """Create or update a WhatsApp Template record and push it to Glific.

    Args:
        template_name:   Human-readable template name (used as Frappe doc name)
        message:         Template body with {{1}}, {{2}} placeholders
        language:        Language for Glific (English / Hindi / Marathi)
        category:        WhatsApp category (UTILITY / MARKETING / AUTHENTICATION)
        glific_shortcode: Override auto-generated shortcode
        force_push:      Re-push even if already pushed

    Returns:
        {
          "status": "ok" | "error",
          "template_name": ...,
          "glific_db_id": ...,
          "glific_shortcode": ...,
          "glific_push_status": "Pushed" | ...,
          "message": "..."
        }
    """
    frappe.logger("tap_buddy_glific").info(
        f"[TEMPLATE-SERVICE] create_and_push_template called: name={template_name!r}"
    )

    shortcode = glific_shortcode or _slugify(template_name)

    # ── 1. Upsert Frappe DocType record ──────────────────────────────────────
    existing = frappe.db.get_value(
        "WhatsApp Template", template_name, ["name", "glific_push_status", "glific_db_id"],
        as_dict=True
    )

    if existing:
        doc = frappe.get_doc("WhatsApp Template", template_name)
        # Update fields if provided
        updates = {}
        if message:
            updates["message"] = message
        if language:
            updates["language"] = language
        if category:
            updates["category"] = category
        if shortcode:
            updates["glific_shortcode"] = shortcode
        if updates:
            updates["detected_params"] = _detect_params(doc.get("message") or message or "")
            doc.update(updates)
            doc.save(ignore_permissions=True)
        created_new = False
    else:
        doc = frappe.new_doc("WhatsApp Template")
        doc.update({
            "template_name":   template_name,
            "message":         message,
            "language":        language,
            "category":        category,
            "glific_shortcode": shortcode,
            "glific_template_id": shortcode,  # keep old field in sync
            "glific_push_status": "Not Pushed",
            "detected_params": _detect_params(message or ""),
        })
        doc.insert(ignore_permissions=True)
        created_new = True

    frappe.logger("tap_buddy_glific").info(
        f"[TEMPLATE-SERVICE] Frappe record {'created' if created_new else 'updated'}: {template_name}"
    )

    # ── 2. Skip push if already pushed (unless force_push) ───────────────────
    if not force_push and doc.get("glific_push_status") in ("Pushed", "Approved"):
        return {
            "status":             "ok",
            "template_name":      template_name,
            "glific_db_id":       doc.get("glific_db_id"),
            "glific_shortcode":   doc.get("glific_shortcode") or shortcode,
            "glific_push_status": doc.get("glific_push_status"),
            "message":            "Already pushed to Glific (use force_push=true to re-push)",
        }

    # ── 3. Push to Glific ─────────────────────────────────────────────────────
    try:
        client = GlificClient()
        tmpl = client.create_hsm_template(
            label=template_name,
            shortcode=shortcode,
            body=doc.get("message") or message,
            language=language,
            category=category,
        )

        # Update Frappe record with Glific response
        doc.update({
            "glific_db_id":       str(tmpl.get("id") or ""),
            "glific_shortcode":   tmpl.get("shortcode") or shortcode,
            "glific_template_id": tmpl.get("shortcode") or shortcode,
            "glific_push_status": "Pushed",
            "glific_push_response": frappe.as_json(tmpl)[:500],
        })
        doc.save(ignore_permissions=True)

        frappe.logger("tap_buddy_glific").info(
            f"[TEMPLATE-SERVICE] Glific push OK: id={tmpl.get('id')} "
            f"shortcode={tmpl.get('shortcode')} status={tmpl.get('status')}"
        )

        return {
            "status":             "ok",
            "template_name":      template_name,
            "glific_db_id":       str(tmpl.get("id") or ""),
            "glific_shortcode":   tmpl.get("shortcode") or shortcode,
            "glific_push_status": "Pushed",
            "glific_template_status": tmpl.get("status"),   # PENDING / APPROVED
            "message":            (
                f"Template pushed to Glific. Status: {tmpl.get('status')}. "
                "If PENDING, WhatsApp approval takes 24-48 hours."
            ),
        }

    except (GlificTerminalError, GlificAPIError) as exc:
        error_msg = str(exc)
        frappe.logger("tap_buddy_glific").error(
            f"[TEMPLATE-SERVICE] Glific push failed for {template_name!r}: {error_msg}"
        )
        # Update push status to reflect error
        try:
            doc.update({
                "glific_push_status": "Not Pushed",
                "glific_push_response": error_msg[:500],
            })
            doc.save(ignore_permissions=True)
        except Exception:
            pass

        return {
            "status":  "error",
            "template_name": template_name,
            "error":   error_msg,
            "message": f"Glific push failed: {error_msg}",
        }


# ---------------------------------------------------------------------------
# API: send_test_message
# ---------------------------------------------------------------------------

@frappe.whitelist()
def send_test_message(
    phone: str,
    parent_name: str = "Parent",
    student_name: str = "Student",
    meeting_date: str = "30 May 2026",
    meeting_time: str = "10:00 AM",
    template_shortcode: str = "pta_meeting_alert_v2",
):
    """Send a test HSM WhatsApp message to the given phone number.

    Uses the approved ``pta_meeting_alert_v2`` template by default (immediate
    delivery). Pass a different ``template_shortcode`` to use another approved
    template.

    Args:
        phone:             Recipient phone (any format — will be normalised)
        parent_name:       {{1}} parameter
        student_name:      {{2}} parameter
        meeting_date:      {{3}} parameter (e.g. "30 May 2026")
        meeting_time:      {{4}} parameter (e.g. "10:00 AM")
        template_shortcode: Glific shortcode to use for sending

    Returns:
        {
          "status": "ok" | "error",
          "message_id": "...",
          "bsp_status": "...",
          "phone": "...",
          "template_used": "...",
          "message": "..."
        }
    """
    frappe.logger("tap_buddy_glific").info(
        f"[TEMPLATE-SERVICE] send_test_message phone={phone!r} template={template_shortcode!r}"
    )

    try:
        client = GlificClient()
        msg = client.send_pta_template(
            phone=phone,
            parent_name=parent_name,
            student_name=student_name,
            meeting_date=meeting_date,
            meeting_time=meeting_time,
            template_name=template_shortcode,
        )

        frappe.logger("tap_buddy_glific").info(
            f"[TEMPLATE-SERVICE] Test message sent OK: "
            f"id={msg.get('id')} bspStatus={msg.get('bspStatus')} phone={phone}"
        )

        return {
            "status":        "ok",
            "message_id":    str(msg.get("id") or ""),
            "bsp_message_id": str(msg.get("bspMessageId") or ""),
            "bsp_status":    msg.get("bspStatus") or "sent",
            "phone":         phone,
            "template_used": template_shortcode,
            "sent_at":       str(now_datetime()),
            "message":       f"✅ Message sent to {phone} via template '{template_shortcode}'",
        }

    except (GlificTerminalError, GlificAPIError) as exc:
        error_msg = str(exc)
        frappe.logger("tap_buddy_glific").error(
            f"[TEMPLATE-SERVICE] send_test_message failed phone={phone}: {error_msg}"
        )
        return {
            "status":  "error",
            "phone":   phone,
            "error":   error_msg,
            "message": f"Send failed: {error_msg}",
        }
