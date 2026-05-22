# Copyright (c) 2026, Nigam and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from tap_buddy.services.lms_ingestion import enqueue_lms_events, process_lms_event
from tap_buddy.services.lms_mapper import handle_lms_event


class IntegrationTestLMSEventMapping(IntegrationTestCase):
    def test_handle_lms_event_log_only(self):
        mapping = _create_mapping(action="Log Only")
        payload = {"event_type": mapping.event_type}
        log = _create_log(mapping.event_type, payload)

        outcome = handle_lms_event(log, payload)

        self.assertEqual(outcome.get("status"), "Processed")
        self.assertEqual(outcome.get("mapping"), mapping.name)

    def test_handle_lms_event_create_campaign_single_school(self):
        school = _create_school()
        template = _create_template()
        mapping = _create_mapping(
            action="Create Campaign",
            template=template.name,
            targeting_type="Single School",
            school_name_key="school_name",
        )
        payload = {"event_type": mapping.event_type, "school_name": school.school_name}
        log = _create_log(mapping.event_type, payload)

        outcome = handle_lms_event(log, payload)

        self.assertEqual(outcome.get("status"), "Processed")
        campaign = frappe.get_doc("TAP Campaign", outcome.get("campaign"))
        self.assertEqual(campaign.school_name, school.name)
        self.assertEqual(campaign.template, template.name)

    def test_handle_lms_event_create_campaign_school_group(self):
        template = _create_template()
        group = _create_school_group()
        mapping = _create_mapping(
            action="Create Campaign",
            template=template.name,
            targeting_type="School Group",
            school_group_key="school_group",
        )
        payload = {"event_type": mapping.event_type, "school_group": group.group_name}
        log = _create_log(mapping.event_type, payload)

        outcome = handle_lms_event(log, payload)

        self.assertEqual(outcome.get("status"), "Processed")
        campaign = frappe.get_doc("TAP Campaign", outcome.get("campaign"))
        self.assertEqual(campaign.school_group, group.name)

    def test_process_lms_event_missing_event_type(self):
        log = _create_log(None, {"payload": "no event type"})

        process_lms_event(log.name)

        updated = frappe.get_doc("LMS Trigger Log", log.name)
        self.assertEqual(updated.status, "Failed")
        self.assertEqual(updated.error, "Missing event_type")

    def test_enqueue_lms_events_deduplicates_by_event_id(self):
        payload = {"event_type": "test.event", "event_id": "evt-123"}

        with patch("frappe.enqueue") as enqueue_mock:
            first = enqueue_lms_events(payload)
            second = enqueue_lms_events(payload)

        self.assertEqual(first[0], second[0])
        count = frappe.db.count("LMS Trigger Log", filters={"event_id": "evt-123"})
        self.assertEqual(count, 1)
        self.assertGreaterEqual(enqueue_mock.call_count, 1)


def _create_school(whatsapp_number="+919999999999"):
    name = f"Test School {frappe.generate_hash(length=6)}"
    school = frappe.get_doc(
        {
            "doctype": "School",
            "school_name": name,
            "principal_name": "Test Principal",
            "whatsapp_number": whatsapp_number,
            "state": "Test State",
            "district": "Test District",
            "udise_code": frappe.generate_hash(length=10),
            "block": "Test Block",
        }
    ).insert(ignore_permissions=True)
    return school


def _create_school_group():
    school = _create_school()
    group_name = f"Group {frappe.generate_hash(length=6)}"
    group = frappe.get_doc(
        {
            "doctype": "School Group",
            "group_name": group_name,
            "is_active": 1,
            "members": [
                {
                    "doctype": "School Group Member",
                    "school": school.name,
                }
            ],
        }
    ).insert(ignore_permissions=True)
    return group


def _create_template():
    name = f"Template {frappe.generate_hash(length=6)}"
    template = frappe.get_doc(
        {
            "doctype": "WhatsApp Template",
            "template_name": name,
            "message": "Hello {{ school_name }}",
        }
    ).insert(ignore_permissions=True)
    return template


def _create_mapping(
    action="Log Only",
    template=None,
    targeting_type="Single School",
    school_name_key=None,
    school_group_key=None,
):
    event_type = f"event.{frappe.generate_hash(length=6)}"
    mapping = frappe.get_doc(
        {
            "doctype": "LMS Event Mapping",
            "event_type": event_type,
            "enabled": 1,
            "action": action,
            "campaign_name_prefix": "LMS",
            "template": template,
            "targeting_type": targeting_type,
            "school_name_key": school_name_key,
            "school_group_key": school_group_key,
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
