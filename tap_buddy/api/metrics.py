import frappe
from frappe.utils import now_datetime


@frappe.whitelist()
def get_summary():
    frappe.only_for("System Manager")

    campaign_total = frappe.db.count("TAP Campaign")
    recipient_total = frappe.db.count("Campaign Recipient")
    recipient_sent = frappe.db.count("Campaign Recipient", {"status": "Sent"})
    recipient_delivered = frappe.db.count(
        "Campaign Recipient", {"status": ["in", ["Delivered", "Read"]]}
    )
    recipient_failed = frappe.db.count("Campaign Recipient", {"status": "Failed"})

    webhook_pending = frappe.db.count("Webhook Event", {"processed": 0})
    webhook_failed = frappe.db.count("Webhook Event", {"processed": 1, "error": ["!=", ""]})

    lms_pending = frappe.db.count("LMS Trigger Log", {"status": "Pending"})
    lms_failed = frappe.db.count("LMS Trigger Log", {"status": ["in", ["Failed", "Skipped"]]})

    glific_sync = frappe.get_single("Glific Sync Settings")

    return {
        "generated_at": now_datetime(),
        "campaigns": {
            "total": campaign_total,
        },
        "recipients": {
            "total": recipient_total,
            "sent": recipient_sent,
            "delivered": recipient_delivered,
            "failed": recipient_failed,
        },
        "webhooks": {
            "pending": webhook_pending,
            "failed": webhook_failed,
        },
        "lms": {
            "pending": lms_pending,
            "failed": lms_failed,
        },
        "glific": {
            "enabled": bool(glific_sync.enabled),
            "dry_run": bool(glific_sync.dry_run),
            "last_synced_at": glific_sync.last_synced_at,
        },
    }
