from unittest.mock import patch
from typing import Any, cast

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime

# On IntegrationTestCase, the doctype test records and all
# link-field test record dependencies are recursively loaded
EXTRA_TEST_RECORD_DEPENDENCIES = []  
IGNORE_TEST_RECORD_DEPENDENCIES = [] 


class IntegrationTestTAPCampaignE2E(IntegrationTestCase):
	"""
	End-to-End Simulation of the TAP Buddy Campaign Lifecycle.
	Proves the queue-first architecture, dispatcher transitions, and sweeper.
	"""

	def setUp(self):
		_set_settings()
		_clear_rate_limit_bucket()

	def test_e2e_campaign_lifecycle(self):
		# =====================================================================
		# PHASE 1: DATA SETUP
		# =====================================================================
		# 1. Create a template
		template = cast(Any, _create_template("E2E Test Template", "Hello {{ school_name }}, welcome to TAP Buddy E2E!"))
		
		# 2. Create 3 Schools first
		schools = []
		for i in range(3):
			school = cast(Any, _create_school(f"E2E School {i} {frappe.generate_hash(length=4)}", f"+91999999999{i}"))
			schools.append(school)

		# 3. Create a School Group with members
		group_name = f"E2E Cohort {frappe.generate_hash(length=6)}"
		group = cast(Any, frappe.get_doc({
			"doctype": "School Group",
			"group_name": group_name,
			"is_active": 1,
			"members": [
				{"school": s.name} for s in schools
			]
		}).insert(ignore_permissions=True))

		# =====================================================================
		# PHASE 2: QUEUE-FIRST WORKFLOW
		# =====================================================================
		# 4. Create and Submit Campaign
		campaign_name = f"E2E Campaign {frappe.generate_hash(length=6)}"
		campaign = cast(Any, frappe.get_doc({
			"doctype": "TAP Campaign",
			"campaign_name": campaign_name,
			"targeting_type": "School Group",
			"school_group": group.name,
			"template": template.name,
			"send_date": now_datetime(),
		}))
		
		# In Frappe tests, doc.insert() triggers validate and before_save.
		# doc.submit() triggers on_submit.
		campaign.insert(ignore_permissions=True)
		campaign.submit()

		# Assert Campaign is Queued
		campaign.reload()
		self.assertEqual(campaign.status, "Queued", "Campaign should be Queued after submission.")

		# Assert NO recipients exist yet (proving queue-first behavior)
		recipient_count = frappe.db.count("Campaign Recipient", filters={"campaign": campaign.name})
		self.assertEqual(recipient_count, 0, "No recipients should be created synchronously on submit.")

		# =====================================================================
		# PHASE 3: DISPATCHER EXECUTION (BACKGROUND WORKER SIMULATION)
		# =====================================================================
		# Mock Glific API to simulate successful sending
		with patch("tap_buddy.services.glific_client.GlificClient.send_message") as send_mock:
			send_mock.return_value = {"id": "mock_e2e_msg_123"}
			
			from tap_buddy.tasks.scheduler import dispatch_campaign
			
			# Trigger the background job
			dispatch_campaign(campaign.name)

		# Assert 3 recipients were created and processed
		recipients = cast(Any, frappe.get_all("Campaign Recipient", filters={"campaign": campaign.name}, fields=["status"]))
		self.assertEqual(len(recipients), 3, "Dispatcher should create exactly 3 recipients.")
		
		# Assert all are 'Sent'
		for r in recipients:
			self.assertEqual(r.status, "Sent", "Recipient should be marked Sent after successful dispatch.")

		# Assert 3 Message Logs were created
		logs = cast(Any, frappe.get_all("Message Log", filters={"campaign": campaign.name}, fields=["status", "provider_message_id"]))
		self.assertEqual(len(logs), 3, "Dispatcher should create exactly 3 Message Logs.")
		for log in logs:
			self.assertEqual(log.status, "Sent")
			self.assertEqual(log.provider_message_id, "mock_e2e_msg_123")

		# =====================================================================
		# PHASE 4: CAMPAIGN COMPLETION SYNC
		# =====================================================================
		# Trigger the hourly sync job
		from tap_buddy.tasks.scheduler import sync_campaign_counts
		sync_campaign_counts()

		campaign.reload()
		self.assertEqual(campaign.status, "Completed", "Campaign should be marked Completed once all recipients are terminal.")
		self.assertEqual(campaign.total_recipients, 3)
		self.assertEqual(campaign.sent_count, 3)

		# =====================================================================
		# PHASE 5: STALE PROCESSING SWEEPER VALIDATION
		# =====================================================================
		# Create a dummy recipient artificially stuck in "Processing"
		stuck_recipient = cast(Any, frappe.get_doc({
			"doctype": "Campaign Recipient",
			"campaign": campaign.name,
			"school": schools[0].name,
			"status": "Processing",
			"retry_count": 0
		}).insert(ignore_permissions=True))

		# Backdate its modified time to 1 hour ago
		import datetime
		frappe.db.sql(
			"UPDATE `tabCampaign Recipient` SET modified = %s WHERE name = %s",
			(now_datetime() - datetime.timedelta(hours=1), stuck_recipient.name)
		)
		
		# Run the retry failed messages scheduler which invokes the sweeper
		from tap_buddy.tasks.scheduler import retry_failed_messages
		# We need to mock send_message again just in case there are other Failed ones, though we only want to test the sweeper side effects
		with patch("tap_buddy.services.glific_client.GlificClient.send_message") as send_mock:
			send_mock.return_value = {"id": "mock_retry"}
			retry_failed_messages()

		# The stuck recipient should now be marked Failed
		stuck_recipient.reload()
		self.assertEqual(stuck_recipient.status, "Pending", "Stale Processing recipient should be marked Pending by the sweeper.")
		self.assertFalse(stuck_recipient.failure_reason)


# ==============================================================================
# Helper Functions
# ==============================================================================

def _create_school(name, whatsapp_number):
	return frappe.get_doc({
		"doctype": "School",
		"school_name": name,
		"principal_name": "E2E Principal",
		"whatsapp_number": whatsapp_number,
		"state": "Test State",
		"district": "Test District",
		"udise_code": frappe.generate_hash(length=10),
		"block": "Test Block",
	}).insert(ignore_permissions=True)


def _create_template(name, message):
	return frappe.get_doc({
		"doctype": "WhatsApp Template",
		"template_name": f"{name} {frappe.generate_hash(length=4)}",
		"message": message,
	}).insert(ignore_permissions=True)


def _set_settings():
	settings = frappe.get_single("TAP Buddy Settings")
	settings.glific_url = "https://api.glific.test/v1"
	settings.glific_token = "test-token"
	settings.batch_size = 50
	settings.rate_limit = 50
	settings.retry_count = 3
	settings.dispatch_start_hour = "00:00:00"
	settings.dispatch_end_hour = "23:59:59"
	settings.sync_mode_fallback = 0 # Ensure we are testing the queue flow!
	settings.save(ignore_permissions=True)


def _clear_rate_limit_bucket():
	stamp = now_datetime()
	bucket = stamp.strftime("%Y%m%d%H%M")
	cache = cast(Any, frappe.cache())  # type: ignore
	cache.delete_value(f"tap_buddy:dispatch_rate:{bucket}")
