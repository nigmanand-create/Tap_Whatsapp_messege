# Copyright (c) 2026, Nigam and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime


# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
# Use these module variables to add/remove to/from that list
EXTRA_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]
IGNORE_TEST_RECORD_DEPENDENCIES = []  # eg. ["User"]



class IntegrationTestTAPCampaign(IntegrationTestCase):
	"""
	Integration tests for TAPCampaign.
	Use this class for testing interactions between multiple components.
	"""

	def test_dispatch_creates_attempt_and_log(self):
		school = _create_school()
		template = _create_template()
		campaign = _create_campaign(school.name, template.name)
		_set_settings()
		_clear_rate_limit_bucket()

		frappe.db.set_value("TAP Campaign", campaign.name, "status", "Scheduled")

		with patch("tap_buddy.services.glific_client.GlificClient.send_message") as send_mock:
			send_mock.return_value = {"id": "msg-123"}
			from tap_buddy.tasks.scheduler import dispatch_campaign

			dispatch_campaign(campaign.name)

		recipients = frappe.get_all(
			"Campaign Recipient",
			filters={"campaign": campaign.name},
			fields=["status", "sent_time"],
		)
		self.assertEqual(len(recipients), 1)
		self.assertEqual(recipients[0].status, "Sent")
		self.assertIsNotNone(recipients[0].sent_time)

		attempts = frappe.get_all(
			"Dispatch Attempt",
			filters={"campaign": campaign.name},
			fields=["status", "provider_message_id"],
		)
		self.assertEqual(len(attempts), 1)
		self.assertEqual(attempts[0].status, "Sent")
		self.assertEqual(attempts[0].provider_message_id, "msg-123")

		logs = frappe.get_all(
			"Message Log",
			filters={"campaign": campaign.name},
			fields=["status", "message"],
		)
		self.assertEqual(len(logs), 1)
		self.assertEqual(logs[0].status, "Sent")
		self.assertIn(school.school_name, logs[0].message)

	def test_retry_runs_after_campaign_sent(self):
		school = _create_school()
		template = _create_template()
		campaign = _create_campaign(school.name, template.name)
		_set_settings()
		_clear_rate_limit_bucket()

		frappe.db.set_value("TAP Campaign", campaign.name, "status", "Scheduled")
		recipient = _create_recipient(campaign.name, school.name, "Failed", 0)

		# Diagnostic: print state before retry
		print("--- DIAG BEFORE RETRY ---")
		print("recipient:", frappe.get_doc("Campaign Recipient", recipient.name).as_dict())
		print("campaign status:", frappe.get_value("TAP Campaign", campaign.name, "status"))
		settings = frappe.get_single("TAP Buddy Settings")
		print("settings:", {"retry_count": settings.retry_count, "rate_limit": settings.rate_limit})

		with patch("tap_buddy.services.glific_client.GlificClient.send_message") as send_mock:
			send_mock.return_value = {"id": "msg-456"}
			from tap_buddy.tasks.scheduler import retry_failed_messages

			retry_failed_messages()

		# Diagnostic: print state after retry
		print("--- DIAG AFTER RETRY ---")
		print("recipient:", frappe.get_doc("Campaign Recipient", recipient.name).as_dict())
		attempts = frappe.get_all("Dispatch Attempt", filters={"campaign": campaign.name}, fields=["name", "status", "provider_message_id"]) 
		logs = frappe.get_all("Message Log", filters={"campaign": campaign.name}, fields=["name", "status", "provider_message_id"]) 
		print("dispatch_attempts:", attempts)
		print("message_logs:", logs)

		status = frappe.get_value("Campaign Recipient", recipient.name, "status")
		self.assertEqual(status, "Sent")

	def test_rate_limit_caps_dispatch_per_minute(self):
		school = _create_school()
		school_two = _create_school()
		template = _create_template()
		campaign = _create_campaign(school.name, template.name)
		_set_settings(rate_limit=1)
		_create_recipient(campaign.name, school_two.name, "Pending", 0)

		frappe.db.set_value("TAP Campaign", campaign.name, "status", "Scheduled")

		fixed_now = now_datetime()
		_clear_rate_limit_bucket(fixed_now)
		with patch("tap_buddy.tasks.scheduler.now_datetime") as now_mock:
			now_mock.return_value = fixed_now
			with patch("tap_buddy.services.glific_client.GlificClient.send_message") as send_mock:
				send_mock.return_value = {"id": "msg-789"}
				from tap_buddy.tasks.scheduler import dispatch_campaign

				dispatch_campaign(campaign.name)

		sent = frappe.db.count(
			"Campaign Recipient",
			filters={"campaign": campaign.name, "status": "Sent"},
		)
		pending = frappe.db.count(
			"Campaign Recipient",
			filters={"campaign": campaign.name, "status": "Pending"},
		)
		self.assertEqual(sent, 1)
		self.assertEqual(pending, 1)

	def test_claim_prevents_duplicate_dispatch(self):
		school = _create_school()
		template = _create_template()
		campaign = _create_campaign(school.name, template.name)
		_set_settings()
		_clear_rate_limit_bucket()
		recipient = _create_recipient(campaign.name, school.name, "Pending", 0)

		with patch("tap_buddy.services.glific_client.GlificClient.send_message") as send_mock:
			send_mock.return_value = {"id": "msg-101"}
			from tap_buddy.tasks.scheduler import dispatch_campaign
			
			frappe.db.set_value("Campaign Recipient", recipient.name, "status", "Pending")
			frappe.db.set_value("TAP Campaign", campaign.name, "status", "Scheduled")
			dispatch_campaign(campaign.name)
			dispatch_campaign(campaign.name)

		self.assertEqual(send_mock.call_count, 1)
		attempts = frappe.db.count(
			"Dispatch Attempt",
			filters={"campaign": campaign.name},
		)
		self.assertEqual(attempts, 1)

	def test_non_retryable_failure_does_not_increment_retry(self):
		school = _create_school()
		template = _create_template()
		campaign = _create_campaign(school.name, template.name)
		_set_settings()
		recipient = _create_recipient(campaign.name, school.name, "Pending", 0)

		from tap_buddy.tasks.scheduler import _dispatch_recipient
		from tap_buddy.services.glific_client import GlificClient
		client = GlificClient()

		payload = frappe._dict({"name": recipient.name, "school": recipient.school, "retry_count": 0})
		with patch("tap_buddy.tasks.scheduler._render_message", return_value=""):
			_dispatch_recipient(client, campaign, payload)

		retry_count = frappe.get_value("Campaign Recipient", recipient.name, "retry_count")
		status = frappe.get_value("Campaign Recipient", recipient.name, "status")
		self.assertEqual(retry_count, 0)
		self.assertEqual(status, "Failed")


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


def _create_campaign(school_name, template_name, message_template="Hello {{ school_name }}"):
	name = f"Campaign {frappe.generate_hash(length=6)}"
	campaign = frappe.get_doc(
		{
			"doctype": "TAP Campaign",
			"campaign_name": name,
			"school_name": school_name,
			"template": template_name,
			"message_template": message_template,
			"send_date": now_datetime(),
			"targeting_type": "Single School",
		}
	).insert(ignore_permissions=True)
	return campaign


def _create_recipient(campaign_name, school_name, status, retry_count):
	recipient = frappe.get_doc(
		{
			"doctype": "Campaign Recipient",
			"campaign": campaign_name,
			"school": school_name,
			"status": status,
			"retry_count": retry_count,
		}
	).insert(ignore_permissions=True)
	return recipient


def _set_settings(rate_limit=5):
	settings = frappe.get_single("TAP Buddy Settings")
	settings.glific_url = "https://api.glific.test/v1"
	settings.glific_token = "test-token"
	settings.batch_size = 5
	settings.rate_limit = rate_limit
	settings.retry_count = 1
	settings.dispatch_start_hour = "00:00:00"
	settings.dispatch_end_hour = "23:59:59"
	settings.save(ignore_permissions=True)


def _clear_rate_limit_bucket(at_time=None):
	from tap_buddy.services.redis_utils import get_redis_conn, PREFIX
	conn = get_redis_conn()
	key = f"{PREFIX}rate_limit:dispatch_limit"
	conn.delete(getattr(conn, "make_key", lambda x: x)(key) if hasattr(conn, "make_key") else key)
