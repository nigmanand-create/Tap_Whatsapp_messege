import frappe
from tap_buddy.services.glific_client import GlificClient
from tap_buddy.wgas.glific_sync_batches import (
	SYNC_GRAPHQL_TIMEOUT,
	_upsert_collection,
	_upsert_wa_group,
)
import traceback


def sync_collections_and_groups():
	"""
	Fetches Group Collections and WhatsApp Groups from Glific (paginated),
	then idempotently upserts them and their mappings into TAP Buddy.
	"""
	frappe.logger("tap_buddy_sync").info("Starting WhatsApp Group Collection Sync")
	try:
		client = GlificClient()

		collections_data = client.get_group_collections(timeout=SYNC_GRAPHQL_TIMEOUT)
		for col in collections_data:
			_upsert_collection(col)
		frappe.db.commit()

		wa_groups_data = client.get_whatsapp_groups(timeout=SYNC_GRAPHQL_TIMEOUT)
		for idx, wag in enumerate(wa_groups_data, start=1):
			_upsert_wa_group(wag)
			if idx % 50 == 0:
				frappe.db.commit()

		frappe.db.commit()
		frappe.logger("tap_buddy_sync").info(
			f"WhatsApp Group Collection Sync completed. Collections: {len(collections_data)}, Groups: {len(wa_groups_data)}"
		)
		return {
			"status": "success",
			"collections_synced": len(collections_data),
			"groups_synced": len(wa_groups_data),
		}

	except Exception as e:
		frappe.db.rollback()
		error_trace = traceback.format_exc()
		frappe.logger("tap_buddy_sync").error(f"WhatsApp Group Collection Sync failed: {str(e)}\n{error_trace}")
		return {"status": "error", "message": str(e)}


@frappe.whitelist()
def trigger_manual_sync():
	"""Triggered via the 'Sync With Glific' UI button."""
	frappe.has_permission("WhatsApp Group Collection", throw=True)
	frappe.enqueue(
		"tap_buddy.services.group_collection_sync.sync_collections_and_groups",
		queue="long",
		timeout=3600,
	)
	return "Sync initiated in background."
