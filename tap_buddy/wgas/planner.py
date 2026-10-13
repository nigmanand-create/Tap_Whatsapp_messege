from __future__ import annotations

import frappe
from frappe.utils import now_datetime

from tap_buddy.utils.constants import STATUS_SCHEDULED


def provision_plan_campaigns(plan_name: str) -> str:
	plan = frappe.get_doc("WGAS Plan", plan_name)
	if not plan.items:
		frappe.throw("No items to schedule. Import Excel first.")

	settings = frappe.get_single("WGAS Settings")
	created = 0
	failed = 0

	plan.db_set("status", "Scheduling")

	for item in plan.items:
		if item.status not in ("Pending", "Failed"):
			continue
		if not item.whatsapp_group:
			_update_item(item, status="Skipped", error_message=item.error_message or "Missing WhatsApp Group")
			failed += 1
			continue

		try:
			campaign_name = _create_campaign_for_item(plan, item, settings)
			_update_item(
				item,
				status="Scheduled",
				tap_campaign=campaign_name,
				error_message=None,
			)
			created += 1
		except Exception as exc:
			frappe.log_error(title=f"WGAS schedule failed row {item.source_row}", message=frappe.get_traceback())
			_update_item(item, status="Failed", error_message=str(exc))
			failed += 1

	from tap_buddy.tap_buddy.doctype.wgas_plan.wgas_plan import update_plan_stats

	update_plan_stats(plan.name)
	return f"Scheduled {created} campaign(s); {failed} failed/skipped."


def _create_campaign_for_item(plan, item, settings) -> str:
	group_doc = frappe.get_doc("WhatsApp Group", item.whatsapp_group)
	title = plan.plan_title or plan.name
	campaign_name = f"WGAS {title} R{item.source_row} {group_doc.group_name}"[:140]

	campaign = frappe.new_doc("TAP Campaign")
	campaign.campaign_name = campaign_name
	campaign.campaign_type = "Template"
	campaign.targeting_type = "WhatsApp Group"
	campaign.target_group = item.whatsapp_group
	campaign.send_date = item.scheduled_at
	campaign.status = STATUS_SCHEDULED
	campaign.wgas_plan = plan.name
	campaign.wgas_plan_item = item.name

	if item.dispatch_mode == "Flow" and item.glific_flow:
		campaign.campaign_type = "Flow"
		campaign.glific_flow = item.glific_flow
		if item.message:
			campaign.flow_custom_parameters = frappe.as_json({"message": item.message})
	elif item.dispatch_mode == "Flow" and item.flow_ref and not item.glific_flow:
		frappe.throw(f"Glific Flow not found for: {item.flow_ref}")

	if campaign.campaign_type != "Flow":
		campaign.campaign_type = "Template"
		if item.message:
			campaign.plain_message_body = item.message
		if settings.fallback_template:
			campaign.template = settings.fallback_template
		elif not item.message:
			frappe.throw("Row needs either a flow or a message.")

	campaign.insert(ignore_permissions=True)
	campaign.submit()
	return campaign.name


def _update_item(item, **kwargs):
	row_name = item.name
	if not row_name:
		return
	frappe.db.set_value("WGAS Plan Item", row_name, kwargs)
