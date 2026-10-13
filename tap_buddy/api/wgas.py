import frappe

from tap_buddy.wgas.engagement import refresh_plan_engagement
from tap_buddy.wgas.excel_import import import_excel_into_plan
from tap_buddy.wgas.planner import provision_plan_campaigns


@frappe.whitelist()
def import_plan(plan_name: str):
	frappe.has_permission("WGAS Plan", "write", throw=True)
	return import_excel_into_plan(plan_name)


@frappe.whitelist()
def schedule_plan(plan_name: str):
	frappe.has_permission("WGAS Plan", "write", throw=True)
	return provision_plan_campaigns(plan_name)


@frappe.whitelist()
def refresh_plan(plan_name: str):
	frappe.has_permission("WGAS Plan", "read", throw=True)
	return refresh_plan_engagement(plan_name)


@frappe.whitelist()
def dashboard():
	frappe.has_permission("WGAS Plan", "read", throw=True)

	from tap_buddy.tap_buddy.doctype.wgas_settings.wgas_settings import get_connection_status

	connection = get_connection_status()
	plans = frappe.get_all(
		"WGAS Plan",
		fields=[
			"name",
			"plan_title",
			"status",
			"total_items",
			"scheduled_items",
			"completed_items",
			"failed_items",
			"modified",
		],
		order_by="modified desc",
		limit=50,
	)

	groups = frappe.db.count("WhatsApp Group", {"status": "Active"})
	if not groups:
		groups = frappe.db.count("WhatsApp Group")
	flows = frappe.db.count("Glific Flow", {"is_active": 1})
	if not flows:
		flows = frappe.db.count("Glific Flow")

	return {
		"system": frappe.db.get_single_value("WGAS Settings", "system_name")
		or "WGAS — WhatsApp Group Automation System",
		"connection": connection,
		"counts": {
			"whatsapp_groups": groups,
			"glific_flows": flows,
			"plans_total": len(plans),
			"plans_active": frappe.db.count(
				"WGAS Plan", {"status": ["in", ["Active", "Scheduling", "Imported"]]}
			),
		},
		"plans": plans,
	}
