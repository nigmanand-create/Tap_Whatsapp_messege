import frappe

from tap_buddy.services.replay import (
    replay_failed_lms_events,
    replay_failed_webhook_events,
    replay_lms_event,
    replay_webhook_event,
)


@frappe.whitelist()
def replay_webhook(event_name, force=0):
    frappe.only_for("System Manager")
    return replay_webhook_event(event_name, force=bool(int(force)))


@frappe.whitelist()
def replay_lms(log_name, force=0):
    frappe.only_for("System Manager")
    return replay_lms_event(log_name, force=bool(int(force)))


@frappe.whitelist()
def replay_failed_webhooks(limit=50):
    frappe.only_for("System Manager")
    return replay_failed_webhook_events(limit=int(limit))


@frappe.whitelist()
def replay_failed_lms(limit=50):
    frappe.only_for("System Manager")
    return replay_failed_lms_events(limit=int(limit))
