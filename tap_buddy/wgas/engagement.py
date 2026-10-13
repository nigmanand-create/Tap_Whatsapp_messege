from __future__ import annotations

import frappe
from frappe.utils import now_datetime


def refresh_plan_engagement(plan_name: str) -> str:
	plan = frappe.get_doc("WGAS Plan", plan_name)
	updated = 0

	for item in plan.items:
		if not item.tap_campaign:
			continue
		stats = _sync_item_engagement(plan.name, item)
		frappe.db.set_value(
			"WGAS Plan Item",
			item.name,
			{
				"delivery_status": stats.get("delivery_status"),
				"response_count": stats.get("response_count", 0),
				"reaction_count": stats.get("reaction_count", 0),
				"status": stats.get("item_status", item.status),
			},
		)
		updated += 1

	from tap_buddy.tap_buddy.doctype.wgas_plan.wgas_plan import update_plan_stats

	update_plan_stats(plan.name)
	return f"Refreshed engagement for {updated} item(s)."


def refresh_active_plans():
	for row in frappe.get_all("WGAS Plan", filters={"status": ["in", ["Active", "Scheduling", "Imported"]]}, pluck="name"):
		try:
			refresh_plan_engagement(row)
		except Exception:
			frappe.log_error(title="WGAS engagement refresh", message=frappe.get_traceback())


def record_engagement_from_webhook(campaign_name: str, engagement_type: str, detail: str = "", phone: str = "", provider_message_id: str = ""):
	campaign = frappe.get_doc("TAP Campaign", campaign_name)
	if not getattr(campaign, "wgas_plan", None):
		return

	existing = frappe.db.exists(
		"WGAS Group Engagement",
		{
			"wgas_plan": campaign.wgas_plan,
			"tap_campaign": campaign_name,
			"engagement_type": engagement_type,
			"detail": detail,
			"contact_phone": phone or "",
			"provider_message_id": provider_message_id or "",
		},
	)
	if existing:
		return

	doc = frappe.new_doc("WGAS Group Engagement")
	doc.wgas_plan = campaign.wgas_plan
	doc.plan_item_row = getattr(campaign, "wgas_plan_item", None)
	doc.tap_campaign = campaign_name
	doc.whatsapp_group = campaign.target_group
	doc.engagement_type = engagement_type
	doc.detail = detail
	doc.contact_phone = phone
	doc.provider_message_id = provider_message_id
	doc.recorded_at = now_datetime()
	doc.insert(ignore_permissions=True)


def _sync_item_engagement(plan_name: str, item) -> dict:
	campaign_name = item.tap_campaign
	recipients = frappe.get_all(
		"Campaign Recipient",
		filters={"campaign": campaign_name, "whatsapp_group": item.whatsapp_group},
		fields=["name", "status"],
	)
	recipient_status = recipients[0].status if recipients else "Pending"

	logs = frappe.get_all(
		"Message Log",
		filters={"campaign": campaign_name, "whatsapp_group": item.whatsapp_group},
		fields=["status", "provider_message_id"],
		order_by="creation desc",
		limit=1,
	)
	log_status = logs[0].status if logs else None

	flow_id = None
	if item.glific_flow:
		flow_id = frappe.db.get_value("Glific Flow", item.glific_flow, "flow_id")

	response_count = 0
	if flow_id:
		response_count = frappe.db.count("TAP Poll Response", {"flow_id": flow_id})

	reaction_count = frappe.db.count(
		"WGAS Group Engagement",
		{"wgas_plan": plan_name, "plan_item_row": item.name, "engagement_type": "Reaction"},
	)
	reply_count = frappe.db.count(
		"WGAS Group Engagement",
		{"wgas_plan": plan_name, "plan_item_row": item.name, "engagement_type": ["in", ["Reply", "Flow Response", "Poll Response"]]},
	)
	response_count = max(response_count, reply_count)

	delivery_status = log_status or recipient_status
	item_status = item.status
	if recipient_status in ("Sent", "Delivered", "Read") or log_status in ("Sent", "Delivered", "Read"):
		item_status = "Sent"

	for status_label in ("Delivered", "Read"):
		if recipient_status == status_label or log_status == status_label:
			record_engagement_from_webhook(campaign_name, status_label, detail=f"Auto-sync {status_label}")

	return {
		"delivery_status": delivery_status,
		"response_count": response_count,
		"reaction_count": reaction_count,
		"item_status": item_status,
	}
