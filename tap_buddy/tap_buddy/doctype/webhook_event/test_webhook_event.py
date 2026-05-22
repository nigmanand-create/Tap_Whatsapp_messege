# Copyright (c) 2026, Nigam and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

from tap_buddy.api.metrics import get_summary
from tap_buddy.services.replay import replay_lms_event, replay_webhook_event


class IntegrationTestWebhookEventOps(IntegrationTestCase):
    def test_replay_webhook_event_updates_status(self):
        frappe.set_user("Administrator")
        school = _create_school()
        template = _create_template()
        campaign = _create_campaign(school, template)
        recipient = _create_recipient(campaign, school)
        log = _create_message_log(campaign, school, "whk-test-ops-1")

        event = frappe.get_doc(
            {
                "doctype": "Webhook Event",
                "provider": "Glific",
                "provider_message_id": log.provider_message_id,
                "status": "Delivered",
                "payload": frappe.as_json(
                    {"provider_message_id": log.provider_message_id, "status": "delivered"}
                ),
                "processed": 1,
                "error": "Message Log not found for provider_message_id",
                "received_at": now_datetime(),
            }
        ).insert(ignore_permissions=True)

        result = replay_webhook_event(event.name, force=True)

        updated_log = frappe.get_doc("Message Log", log.name)
        updated_recipient = frappe.get_doc("Campaign Recipient", recipient.name)

        self.assertEqual(result.get("status"), "processed")
        self.assertEqual(updated_log.status, "Delivered")
        self.assertEqual(updated_recipient.status, "Delivered")

    def test_replay_lms_event_processes(self):
        frappe.set_user("Administrator")
        mapping = _create_lms_mapping()
        log = frappe.get_doc(
            {
                "doctype": "LMS Trigger Log",
                "event_type": mapping.event_type,
                "event_id": "evt-replay-1",
                "source": "lms",
                "payload": frappe.as_json({"event_type": mapping.event_type}),
                "received_at": now_datetime(),
                "status": "Failed",
                "error": "Missing event_type",
            }
        ).insert(ignore_permissions=True)

        result = replay_lms_event(log.name, force=True)
        updated = frappe.get_doc("LMS Trigger Log", log.name)

        self.assertEqual(result.get("status"), "Processed")
        self.assertEqual(updated.status, "Processed")
        self.assertEqual(updated.mapping, mapping.name)

    def test_metrics_summary(self):
        frappe.set_user("Administrator")
        summary = get_summary()

        self.assertIn("campaigns", summary)
        self.assertIn("recipients", summary)
        self.assertIn("webhooks", summary)
        self.assertIn("lms", summary)
        self.assertIn("glific", summary)


def _create_school():
    name = f"Ops School {frappe.generate_hash(length=6)}"
    return frappe.get_doc(
        {
            "doctype": "School",
            "school_name": name,
            "principal_name": "Ops Principal",
            "whatsapp_number": "+919999999999",
            "state": "Ops State",
            "district": "Ops District",
            "udise_code": frappe.generate_hash(length=10),
            "block": "Ops Block",
        }
    ).insert(ignore_permissions=True)


def _create_template():
    name = f"Ops Template {frappe.generate_hash(length=6)}"
    return frappe.get_doc(
        {
            "doctype": "WhatsApp Template",
            "template_name": name,
            "message": "Hello {{ school_name }}",
        }
    ).insert(ignore_permissions=True)


def _create_campaign(school, template):
    return frappe.get_doc(
        {
            "doctype": "TAP Campaign",
            "campaign_name": f"Ops Campaign {frappe.generate_hash(length=6)}",
            "school_name": school.name,
            "template": template.name,
            "message_template": template.message,
            "send_date": now_datetime(),
            "targeting_type": "Single School",
        }
    ).insert(ignore_permissions=True)


def _create_recipient(campaign, school):
    return frappe.get_doc(
        {
            "doctype": "Campaign Recipient",
            "campaign": campaign.name,
            "school": school.name,
            "status": "Sent",
            "sent_time": now_datetime(),
        }
    ).insert(ignore_permissions=True)


def _create_message_log(campaign, school, provider_message_id):
    return frappe.get_doc(
        {
            "doctype": "Message Log",
            "campaign": campaign.name,
            "school": school.name,
            "phone_number": "+919999999999",
            "message": "hi",
            "status": "Sent",
            "provider_message_id": provider_message_id,
            "sent_at": now_datetime(),
        }
    ).insert(ignore_permissions=True)


def _create_lms_mapping():
    event_type = f"event.{frappe.generate_hash(length=6)}"
    return frappe.get_doc(
        {
            "doctype": "LMS Event Mapping",
            "event_type": event_type,
            "enabled": 1,
            "action": "Log Only",
            "campaign_name_prefix": "LMS",
        }
    ).insert(ignore_permissions=True)
