import frappe
from frappe.utils import now_datetime

from tap_buddy.services.glific_client import GlificClient, GlificAPIError
from tap_buddy.utils.phone import normalize_phone_number


def sync_glific():
    settings = frappe.get_single("Glific Sync Settings")
    if not settings.enabled:
        return {"status": "disabled"}

    results = {"contacts": 0, "groups": 0}
    max_modified = None

    if settings.sync_contacts:
        contact_result = _sync_contacts(settings)
        results["contacts"] = contact_result.get("processed", 0)
        max_modified = _max_datetime(max_modified, contact_result.get("max_modified"))

    if settings.sync_groups:
        results["groups"] = _sync_groups(settings)

    if max_modified:
        settings.last_synced_at = max_modified
    else:
        settings.last_synced_at = now_datetime()
    settings.save(ignore_permissions=True)

    return results


def _sync_contacts(settings):
    batch_size = settings.batch_size or 100
    mappings = _get_field_mappings()
    filters = {"whatsapp_number": ["!=", ""]}
    if settings.sync_only_new and settings.last_synced_at:
        filters["modified"] = [">", settings.last_synced_at]

    schools = frappe.get_all(
        "School",
        filters=filters,
        fields=[
            "name",
            "school_name",
            "whatsapp_number",
            "state",
            "district",
            "udise_code",
            "block",
            "modified",
        ],
        limit=batch_size,
        order_by="modified desc",
    )

    client = None if settings.dry_run else GlificClient()
    processed = 0
    max_modified = None

    for school in schools:
        payload = _build_contact_payload(school, mappings)
        if not payload.get("phone"):
            continue
        max_modified = _max_datetime(max_modified, school.modified)
        if settings.dry_run:
            processed += 1
            continue
        try:
            client.upsert_contact(payload)
            processed += 1
        except GlificAPIError:
            frappe.log_error(title="Glific Sync Error", message=f"Failed to sync {school.name}")

    return {"processed": processed, "max_modified": max_modified}


def _sync_groups(settings):
    mappings = frappe.get_all(
        "Glific Contact Group Mapping",
        filters={"enabled": 1},
        fields=["name", "school_group", "glific_group_id"],
    )

    if not mappings:
        return 0

    client = None if settings.dry_run else GlificClient()
    processed = 0

    for mapping in mappings:
        group_doc = frappe.get_doc("School Group", mapping.school_group)
        for member in group_doc.members:
            school = frappe.get_doc("School", member.school)
            payload = {
                "name": school.school_name,
                "phone": normalize_phone_number(school.whatsapp_number),
            }
            if not payload.get("phone"):
                continue
            if settings.dry_run:
                processed += 1
                continue
            try:
                contact = client.upsert_contact(payload)
                contact_id = _extract_contact_id(contact)
                if contact_id:
                    client.add_contact_to_group(mapping.glific_group_id, contact_id)
                    processed += 1
            except GlificAPIError:
                frappe.log_error(
                    title="Glific Group Sync Error",
                    message=f"Failed to sync group {mapping.school_group} for {school.name}",
                )

    return processed


def _get_field_mappings():
    return frappe.get_all(
        "Glific Field Mapping",
        filters={"enabled": 1, "source_doctype": "School"},
        fields=["source_field", "glific_field"],
    )


def _build_contact_payload(school, mappings):
    payload = {
        "name": school.school_name,
        "phone": normalize_phone_number(school.whatsapp_number),
        "fields": {},
    }

    for mapping in mappings:
        value = school.get(mapping.source_field)
        if value is None:
            continue
        payload["fields"][mapping.glific_field] = value

    if not payload["fields"]:
        payload.pop("fields")

    return payload


def _extract_contact_id(response):
    if not response:
        return None
    if isinstance(response, dict):
        if "id" in response:
            return response.get("id")
        if "data" in response and isinstance(response["data"], dict):
            return response["data"].get("id")
        if "contact" in response and isinstance(response["contact"], dict):
            return response["contact"].get("id")
    return None


def _max_datetime(current, candidate):
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if candidate > current else current
