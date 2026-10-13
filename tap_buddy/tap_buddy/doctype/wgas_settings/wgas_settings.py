import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime
from frappe.utils.password import get_decrypted_password, set_encrypted_password

_GLIFIC_PASSWORD_FIELDS = (
	"glific_token",
	"glific_access_token",
	"glific_refresh_token",
	"webhook_secret",
)


class WGASSettings(Document):
	def validate(self):
		if not self.glific_url:
			frappe.throw("Glific URL is required for WGAS.")

	def on_update(self):
		# Sync URL/phone/webhooks; copy tokens only when stored on WGAS (empty = keep TAP Buddy tokens).
		_sync_wgas_to_tap_buddy(self)


def _doc_record_name(doc) -> str:
	return doc.name or doc.doctype


def _get_password_safe(doc, fieldname: str) -> str | None:
	return get_decrypted_password(
		doc.doctype, _doc_record_name(doc), fieldname, raise_exception=False
	)


def _set_password_on_doc(doc, fieldname: str, value: str):
	if callable(getattr(doc, "set_password", None)):
		doc.set_password(fieldname, value)
		return
	set_encrypted_password(doc.doctype, _doc_record_name(doc), value, fieldname)


def _copy_password_field(source_doc, target_doc, fieldname: str):
	value = _get_password_safe(source_doc, fieldname)
	if value:
		_set_password_on_doc(target_doc, fieldname, value)


def _sync_wgas_to_tap_buddy(wgas):
	tbs = frappe.get_single("TAP Buddy Settings")
	tbs.glific_url = wgas.glific_url
	tbs.glific_phone_number = wgas.glific_phone_number
	tbs.glific_token_expiry = wgas.glific_token_expiry
	tbs.webhook_enabled = wgas.webhook_enabled or 0
	tbs.webhook_signature_header = wgas.webhook_signature_header or "X-Glific-Signature"

	for field in _GLIFIC_PASSWORD_FIELDS:
		_copy_password_field(wgas, tbs, field)

	tbs.save(ignore_permissions=True)


def _sync_tap_buddy_to_wgas(wgas):
	tbs = frappe.get_single("TAP Buddy Settings")
	wgas.glific_url = tbs.glific_url or wgas.glific_url
	wgas.glific_phone_number = tbs.glific_phone_number
	wgas.glific_token_expiry = tbs.glific_token_expiry
	wgas.webhook_enabled = tbs.webhook_enabled or 0
	wgas.webhook_signature_header = tbs.webhook_signature_header

	for field in _GLIFIC_PASSWORD_FIELDS:
		_copy_password_field(tbs, wgas, field)


def _has_glific_credentials() -> bool:
	for doc in (frappe.get_single("TAP Buddy Settings"), frappe.get_single("WGAS Settings")):
		for field in ("glific_access_token", "glific_token", "glific_refresh_token"):
			if _get_password_safe(doc, field):
				return True
	return False


def _has_webhook_secret() -> bool:
	for doc in (frappe.get_single("TAP Buddy Settings"), frappe.get_single("WGAS Settings")):
		if _get_password_safe(doc, "webhook_secret"):
			return True
	return False


def _persist_connection_status(status: str, message: str):
	frappe.db.set_value(
		"WGAS Settings",
		"WGAS Settings",
		{
			"glific_connection_status": status,
			"glific_last_tested_at": now_datetime(),
			"glific_connection_message": (message or "")[:500],
		},
		update_modified=False,
	)
	frappe.db.commit()


@frappe.whitelist()
def get_connection_status():
	wgas = frappe.get_single("WGAS Settings")
	return {
		"glific_status": wgas.glific_connection_status or "Not Tested",
		"message": wgas.glific_connection_message or "",
		"last_tested_at": wgas.glific_last_tested_at,
		"has_credentials": _has_glific_credentials(),
		"webhook_enabled": bool(wgas.webhook_enabled),
		"has_webhook_secret": _has_webhook_secret(),
		"token_expiry": wgas.glific_token_expiry,
		"glific_url_set": bool(wgas.glific_url),
	}


@frappe.whitelist()
def refresh_connection_status():
	if not frappe.get_single("WGAS Settings").glific_url:
		_persist_connection_status("Not Configured", "Glific URL is missing.")
		return get_connection_status()

	if not _has_glific_credentials():
		_persist_connection_status(
			"Not Configured",
			"No access/refresh token. Click Bootstrap Glific or Load from TAP Buddy Settings.",
		)
		return get_connection_status()

	try:
		wgas = frappe.get_single("WGAS Settings")
		_sync_wgas_to_tap_buddy(wgas)
		frappe.db.commit()
		from tap_buddy.services.glific_client import GlificClient

		client = GlificClient()
		client._graphql_request("query { waGroupsCount }")
		_persist_connection_status("Connected", "Glific API OK (waGroupsCount query succeeded).")
	except Exception as exc:
		_persist_connection_status("Failed", str(exc))

	return get_connection_status()


@frappe.whitelist()
def load_from_tap_buddy():
	wgas = frappe.get_single("WGAS Settings")
	_sync_tap_buddy_to_wgas(wgas)
	if not wgas.glific_url:
		return {
			"status": "skipped",
			"message": "No Glific URL in TAP Buddy Settings yet. Enter credentials here and Save.",
		}
	wgas.save(ignore_permissions=True)
	frappe.db.commit()
	return {"status": "success", "message": "Loaded Glific settings from TAP Buddy Settings."}


@frappe.whitelist()
def bootstrap_glific(password: str):
	from tap_buddy.tap_buddy.doctype.tap_buddy_settings.tap_buddy_settings import bootstrap_glific_session

	wgas = frappe.get_single("WGAS Settings")
	if not wgas.glific_url:
		frappe.throw("Save Glific URL first.")
	phone = wgas.glific_phone_number
	if not phone:
		frappe.throw("Set Glific Login Phone on WGAS Settings.")

	# Ensure TAP Buddy has URL before bootstrap
	_sync_wgas_to_tap_buddy(wgas)
	frappe.db.commit()

	result = bootstrap_glific_session(phone, password)
	if result.get("status") == "success":
		load_from_tap_buddy()
		refresh_connection_status()
	return result


@frappe.whitelist()
def test_glific_connection():
	from tap_buddy.tap_buddy.doctype.tap_buddy_settings.tap_buddy_settings import (
		test_glific_connection as tbs_test,
	)

	wgas = frappe.get_single("WGAS Settings")
	_sync_wgas_to_tap_buddy(wgas)
	frappe.db.commit()
	result = tbs_test()
	if result.get("status") == "success":
		_persist_connection_status("Connected", result.get("message") or "Connection test passed.")
	else:
		_persist_connection_status("Failed", result.get("message") or "Connection test failed.")
	result["indicators"] = get_connection_status()
	return result


@frappe.whitelist()
def sync_whatsapp_groups():
	from tap_buddy.services.group_collection_sync import sync_collections_and_groups

	_sync_wgas_to_tap_buddy(frappe.get_single("WGAS Settings"))
	return sync_collections_and_groups()


@frappe.whitelist()
def sync_glific_flows():
	from tap_buddy.services.flow_sync import sync_glific_flows as run_sync

	return run_sync()
