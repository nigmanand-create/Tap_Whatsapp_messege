import frappe
from tap_buddy.services.glific_client import GlificClient
from tap_buddy.wgas.glific_sync_batches import SYNC_GRAPHQL_TIMEOUT, _upsert_flow


@frappe.whitelist()
def sync_glific_flows():
	"""
	Fetch active flows from Glific (paginated) and upsert into Glific Flow.
	"""
	frappe.logger("tap_buddy_sync").info("Starting Glific flows sync...")
	client = GlificClient()

	try:
		flows = client.get_flows(is_active=True, timeout=SYNC_GRAPHQL_TIMEOUT)
	except Exception:
		frappe.logger("tap_buddy_sync").exception("Failed to fetch flows from Glific")
		return False

	count_upserted = 0
	for idx, flow in enumerate(flows, start=1):
		_upsert_flow(flow)
		count_upserted += 1
		if idx % 50 == 0:
			frappe.db.commit()

	frappe.db.commit()
	frappe.logger("tap_buddy_sync").info(f"Successfully synced {count_upserted} flows.")
	return True
