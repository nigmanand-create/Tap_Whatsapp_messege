import frappe

from tap_buddy.utils.constants import STATUS_COMPLETED, STATUS_QUEUED


def execute():
    logger = frappe.logger("tap_buddy")

    scheduled_rows = frappe.get_all(
        "TAP Campaign",
        filters={"status": "Scheduled"},
        fields=["name"],
    )
    if scheduled_rows:
        names = [row.name for row in scheduled_rows]
        frappe.db.set_value("TAP Campaign", {"name": ["in", names]}, "status", STATUS_QUEUED)
        logger.info("Campaign status migration: Scheduled -> Queued for %s records", len(names))
    else:
        logger.info("Campaign status migration: Scheduled -> Queued for 0 records")

    sent_rows = frappe.get_all(
        "TAP Campaign",
        filters={"status": "Sent"},
        fields=["name"],
    )
    if sent_rows:
        names = [row.name for row in sent_rows]
        frappe.db.set_value("TAP Campaign", {"name": ["in", names]}, "status", STATUS_COMPLETED)
        logger.info("Campaign status migration: Sent -> Completed for %s records", len(names))
    else:
        logger.info("Campaign status migration: Sent -> Completed for 0 records")
