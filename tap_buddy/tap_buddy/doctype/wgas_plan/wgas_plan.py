import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime

from tap_buddy.wgas.excel_import import import_excel_into_plan
from tap_buddy.wgas.planner import provision_plan_campaigns
from tap_buddy.wgas.engagement import refresh_plan_engagement


class WGASPlan(Document):
	def validate(self):
		if not self.timezone:
			self.timezone = "Asia/Kolkata"

	@frappe.whitelist()
	def import_from_excel(self):
		if not self.excel_file:
			frappe.throw("Upload an Excel file first.")
		summary = import_excel_into_plan(self.name)
		self.reload()
		return summary

	@frappe.whitelist()
	def build_schedule(self):
		result = provision_plan_campaigns(self.name)
		self.reload()
		return result

	@frappe.whitelist()
	def refresh_engagement(self):
		result = refresh_plan_engagement(self.name)
		self.reload()
		return result


def update_plan_stats(plan_name: str):
	plan = frappe.get_doc("WGAS Plan", plan_name)
	items = plan.items or []
	total = len(items)
	scheduled = sum(1 for i in items if i.status == "Scheduled")
	completed = sum(1 for i in items if i.status == "Sent")
	failed = sum(1 for i in items if i.status in ("Failed", "Skipped"))
	plan.db_set(
		{
			"total_items": total,
			"scheduled_items": scheduled,
			"completed_items": completed,
			"failed_items": failed,
			"modified": now_datetime(),
		}
	)
	if total and completed == total:
		plan.db_set("status", "Completed")
	elif failed and scheduled == 0 and completed == 0:
		plan.db_set("status", "Failed")
	elif scheduled or completed:
		plan.db_set("status", "Active")
