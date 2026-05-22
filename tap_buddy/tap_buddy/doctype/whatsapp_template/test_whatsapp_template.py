# Copyright (c) 2026, Nigam and Contributors
# See license.txt

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import now_datetime


class IntegrationTestWhatsAppTemplate(IntegrationTestCase):
	def test_create_and_update_template(self):
		name = f"Template {frappe.generate_hash(length=6)}"
		template = frappe.get_doc(
			{
				"doctype": "WhatsApp Template",
				"template_name": name,
				"message": "Hello {{ school_name }}",
			}
		).insert(ignore_permissions=True)

		frappe.db.set_value("WhatsApp Template", template.name, "message", "Updated")
		updated = frappe.get_value("WhatsApp Template", template.name, "message")
		self.assertEqual(updated, "Updated")

	def test_campaign_auto_fills_message_template(self):
		school = _create_school()
		template = _create_template()

		campaign = frappe.get_doc(
			{
				"doctype": "TAP Campaign",
				"campaign_name": f"Campaign {frappe.generate_hash(length=6)}",
				"school_name": school.name,
				"template": template.name,
				"send_date": now_datetime(),
				"targeting_type": "Single School",
				"message_template": "",
			}
		).insert(ignore_permissions=True)

		self.assertEqual(campaign.message_template, template.message)

	def test_single_school_requires_school(self):
		template = _create_template()
		with self.assertRaises(frappe.ValidationError):
			frappe.get_doc(
				{
					"doctype": "TAP Campaign",
					"campaign_name": f"Campaign {frappe.generate_hash(length=6)}",
					"template": template.name,
					"send_date": now_datetime(),
					"targeting_type": "Single School",
					"message_template": "Hello",
				}
			).insert(ignore_permissions=True)


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
