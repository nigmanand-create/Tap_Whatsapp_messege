# Copyright (c) 2026, Nigam and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from tap_buddy.tasks import scheduler


class IntegrationTestLMSScheduler(IntegrationTestCase):
    def test_process_pending_lms_events_marks_processed(self):
        mapping = _create_mapping(action="Log Only")
        log = _create_log(mapping.event_type, {"event_type": mapping.event_type})

        scheduler.process_pending_lms_events()

        updated = frappe.get_doc("LMS Trigger Log", log.name)
        self.assertEqual(updated.status, "Processed")
        self.assertIsNotNone(updated.processed_at)
        self.assertEqual(updated.mapping, mapping.name)

    def test_process_pending_lms_events_skips_if_no_mapping(self):
        log = _create_log("event.no.mapping", {"event_type": "event.no.mapping"})

        scheduler.process_pending_lms_events()

        updated = frappe.get_doc("LMS Trigger Log", log.name)
        self.assertEqual(updated.status, "Skipped")

    def test_process_pending_lms_events_ignores_processed(self):
        mapping = _create_mapping(action="Log Only")
        log = _create_log(mapping.event_type, {"event_type": mapping.event_type})
        frappe.db.set_value("LMS Trigger Log", log.name, "status", "Processed")

        scheduler.process_pending_lms_events()

        updated = frappe.get_doc("LMS Trigger Log", log.name)
        self.assertEqual(updated.status, "Processed")


def _create_mapping(action="Log Only"):
    event_type = f"event.{frappe.generate_hash(length=6)}"
    mapping = frappe.get_doc(
        {
            "doctype": "LMS Event Mapping",
            "event_type": event_type,
            "enabled": 1,
            "action": action,
            "campaign_name_prefix": "LMS",
        }
    ).insert(ignore_permissions=True)
    return mapping


def _create_log(event_type, payload):
    log = frappe.get_doc(
        {
            "doctype": "LMS Trigger Log",
            "event_type": event_type,
            "event_id": payload.get("event_id") if isinstance(payload, dict) else None,
            "source": "lms",
            "payload": frappe.as_json(payload),
            "received_at": now_datetime(),
            "status": "Pending",
        }
    ).insert(ignore_permissions=True)
    return log
