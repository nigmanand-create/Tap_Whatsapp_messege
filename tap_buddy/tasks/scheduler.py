"""Background job entrypoints for TAP Buddy campaign dispatch."""

from __future__ import annotations

import frappe

from tap_buddy.services.recipients import build_campaign_recipients


def dispatch_campaign(campaign_name: str) -> dict[str, object]:
	"""Dispatch a campaign in a safe, minimal way.

	The current implementation keeps the job idempotent and side-effect light:
	it loads the campaign, attempts recipient creation through the recipient
	service, and returns a summary for logging and tests.
	"""
	campaign = frappe.get_doc("TAP Campaign", campaign_name)
	created_recipients = 0

	try:
		created_recipients = build_campaign_recipients(campaign.name)
	except Exception:
		frappe.logger().exception("Failed to build campaign recipients for %s", campaign_name)
		raise

	return {
		"campaign_name": campaign.name,
		"status": getattr(campaign, "status", None),
		"created_recipients": created_recipients,
	}
