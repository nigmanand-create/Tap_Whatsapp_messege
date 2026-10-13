"""Paginated Glific → Desk sync (collections, WA groups, flows)."""

from __future__ import annotations

import frappe
from frappe import _

from tap_buddy.services.glific_client import GlificClient

DEFAULT_PAGE_SIZE = 50
SYNC_GRAPHQL_TIMEOUT = 60


def _upsert_collection(col: dict) -> None:
	col_id = str(col.get("id"))
	col_name = col.get("label", "")
	group_count = col.get("waGroupsCount", 0)

	if not frappe.db.exists("WhatsApp Group Collection", {"glific_collection_id": col_id}):
		doc = frappe.new_doc("WhatsApp Group Collection")
		doc.glific_collection_id = col_id
		doc.collection_name = col_name
		doc.group_count = group_count
		doc.last_synced_at = frappe.utils.now_datetime()
		doc.insert(ignore_permissions=True)
	else:
		doc_name = frappe.db.get_value(
			"WhatsApp Group Collection", {"glific_collection_id": col_id}, "name"
		)
		doc = frappe.get_doc("WhatsApp Group Collection", doc_name)
		doc.collection_name = col_name
		doc.group_count = group_count
		doc.last_synced_at = frappe.utils.now_datetime()
		doc.save(ignore_permissions=True)


def _upsert_wa_group(wag: dict) -> None:
	wag_id = str(wag.get("id"))
	wag_name = wag.get("label", "")
	last_comm_at = wag.get("lastCommunicationAt")
	associated_collections = wag.get("groups") or []

	if not frappe.db.exists("WhatsApp Group", {"glific_group_id": wag_id}):
		wag_doc = frappe.new_doc("WhatsApp Group")
		wag_doc.glific_group_id = wag_id
		wag_doc.group_name = wag_name
		wag_doc.status = "Active"
		if last_comm_at:
			wag_doc.last_communication_at = last_comm_at
		wag_doc.last_synced_at = frappe.utils.now_datetime()
		wag_doc.insert(ignore_permissions=True)
	else:
		wag_name_local = frappe.db.get_value("WhatsApp Group", {"glific_group_id": wag_id}, "name")
		wag_doc = frappe.get_doc("WhatsApp Group", wag_name_local)
		wag_doc.group_name = wag_name
		if last_comm_at:
			wag_doc.last_communication_at = last_comm_at
		wag_doc.last_synced_at = frappe.utils.now_datetime()
		wag_doc.save(ignore_permissions=True)

	frappe.db.sql(
		"DELETE FROM `tabWhatsApp Group Collection Mapping` WHERE whatsapp_group = %s",
		(wag_doc.name,),
	)
	for assoc_col in associated_collections:
		assoc_col_id = str(assoc_col.get("id"))
		col_name_local = frappe.db.get_value(
			"WhatsApp Group Collection", {"glific_collection_id": assoc_col_id}, "name"
		)
		if col_name_local:
			mapping_doc = frappe.new_doc("WhatsApp Group Collection Mapping")
			mapping_doc.collection = col_name_local
			mapping_doc.whatsapp_group = wag_doc.name
			mapping_doc.insert(ignore_permissions=True)


def _upsert_flow(flow: dict) -> None:
	flow_id = str(flow.get("id"))
	if not flow_id:
		return
	doc_data = {
		"doctype": "Glific Flow",
		"flow_id": flow_id,
		"flow_name": flow.get("name") or f"Flow {flow_id}",
		"flow_type": flow.get("flowType"),
		"is_active": flow.get("isActive"),
		"is_background": flow.get("isBackground"),
	}
	if frappe.db.exists("Glific Flow", flow_id):
		doc = frappe.get_doc("Glific Flow", flow_id)
		doc.update(doc_data)
		doc.save(ignore_permissions=True)
	else:
		doc = frappe.get_doc(doc_data)
		doc.insert(ignore_permissions=True)


@frappe.whitelist()
def sync_glific_batch(phase: str, page: int = 1, page_size: int = DEFAULT_PAGE_SIZE):
	"""One page of sync for UI progressive loading (no full-page freeze)."""
	if not frappe.has_permission("WGAS Settings", "read") and not frappe.has_permission(
		"WhatsApp Group Collection", "read"
	):
		frappe.throw(_("Not permitted to run Glific sync."), frappe.PermissionError)

	page = max(int(page), 1)
	page_size = min(max(int(page_size), 1), 200)
	offset = (page - 1) * page_size
	client = GlificClient()

	try:
		if phase == "collections":
			batch = client.get_group_collections_page(
				limit=page_size, offset=offset, timeout=SYNC_GRAPHQL_TIMEOUT
			)
			for col in batch:
				_upsert_collection(col)
			frappe.db.commit()
			has_more = len(batch) >= page_size
			return {
				"phase": phase,
				"page": page,
				"processed": len(batch),
				"has_more": has_more,
				"next_page": page + 1 if has_more else None,
				"message": __("Synced {0} collection(s), page {1}", [len(batch), page]),
			}

		if phase == "wa_groups":
			batch = client.get_whatsapp_groups_page(
				limit=page_size, offset=offset, timeout=SYNC_GRAPHQL_TIMEOUT
			)
			for wag in batch:
				_upsert_wa_group(wag)
			frappe.db.commit()
			has_more = len(batch) >= page_size
			return {
				"phase": phase,
				"page": page,
				"processed": len(batch),
				"has_more": has_more,
				"next_page": page + 1 if has_more else None,
				"message": __("Synced {0} WhatsApp group(s), page {1}", [len(batch), page]),
			}

		if phase == "flows":
			batch = client.get_flows_page(
				is_active=True,
				limit=page_size,
				offset=offset,
				timeout=SYNC_GRAPHQL_TIMEOUT,
			)
			for flow in batch:
				_upsert_flow(flow)
			frappe.db.commit()
			has_more = len(batch) >= page_size
			return {
				"phase": phase,
				"page": page,
				"processed": len(batch),
				"has_more": has_more,
				"next_page": page + 1 if has_more else None,
				"message": __("Synced {0} flow(s), page {1}", [len(batch), page]),
			}

		frappe.throw(f"Unknown sync phase: {phase}")
	except Exception as exc:
		frappe.db.rollback()
		frappe.log_error(title=f"WGAS sync batch {phase} p{page}", message=frappe.get_traceback())
		return {
			"phase": phase,
			"page": page,
			"processed": 0,
			"has_more": False,
			"error": str(exc),
			"message": str(exc),
		}

