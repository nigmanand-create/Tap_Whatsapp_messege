import frappe
from frappe.utils import now_datetime

from tap_buddy.services.glific_client import GlificClient, GlificAPIError
from tap_buddy.utils.phone import normalize_phone_number


def sync_glific():
    settings = frappe.get_single("Glific Sync Settings")
    if not settings.enabled:
        return {"status": "disabled"}

    results = {"contacts": 0, "groups": 0, "memberships": 0}
    max_modified = None

    if settings.sync_contacts:
        contact_result = _sync_contacts(settings)
        results["contacts"] = contact_result.get("processed", 0)
        max_modified = _max_datetime(max_modified, contact_result.get("max_modified"))

    if settings.sync_groups:
        client = None if settings.dry_run else GlificClient()
        group_map = _fetch_and_reconcile_groups(client, settings)
        results["groups"] = len(group_map)
        
        member_result = _sync_group_memberships(client, settings, group_map)
        results["memberships"] = member_result

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


def _fetch_and_reconcile_groups(client, settings):
    """
    Fetches all groups from Glific, detects duplicates/stale mappings, 
    and idempotently creates missing groups.
    """
    glific_groups = {}
    if not settings.dry_run:
        page = 1
        while True:
            try:
                resp = client.get_groups({"page": page, "limit": 100})
                data = resp.get("data", [])
                for g in data:
                    name = g.get("name")
                    if name:
                        glific_groups[name.strip().lower()] = g.get("id")
                
                meta = resp.get("metadata", {})
                if not meta or not meta.get("next_page") or page >= 50:
                    break
                page += 1
            except GlificAPIError as e:
                frappe.log_error(title="Glific Group Fetch Error", message=str(e))
                break

    mappings = frappe.get_all(
        "Glific Contact Group Mapping",
        filters={"enabled": 1},
        fields=["name", "school_group", "glific_group_id"],
    )

    reconciled_map = {}

    for mapping in mappings:
        group_doc = frappe.get_doc("School Group", mapping.school_group)
        group_name = group_doc.group_name.strip()
        lower_name = group_name.lower()
        glific_id = mapping.glific_group_id

        if not settings.dry_run:
            if lower_name in glific_groups:
                actual_id = glific_groups[lower_name]
                if str(glific_id) != str(actual_id):
                    # Stale mapping detected, heal it locally
                    frappe.db.set_value("Glific Contact Group Mapping", mapping.name, "glific_group_id", actual_id)
                    glific_id = actual_id
            else:
                # Missing in Glific. Create idempotently.
                try:
                    resp = client.create_group({"name": group_name, "description": "Auto-synced from TAP Buddy"})
                    new_id = _extract_group_id(resp)
                    if new_id:
                        frappe.db.set_value("Glific Contact Group Mapping", mapping.name, "glific_group_id", new_id)
                        glific_id = new_id
                        glific_groups[lower_name] = new_id
                except GlificAPIError as e:
                    # Could be a race condition from another worker. Fetch again later.
                    frappe.logger("tap_buddy_sync").error(f"Failed to create group {group_name}: {str(e)}")
                    continue

        reconciled_map[mapping.school_group] = glific_id

    frappe.db.commit()
    return reconciled_map


def _sync_group_memberships(client, settings, group_map):
    """
    Syncs memberships safely, ensuring contacts are upserted before association.
    """
    processed = 0
    if not group_map:
        return 0

    for school_group_id, glific_group_id in group_map.items():
        if not glific_group_id:
            continue
            
        try:
            group_doc = frappe.get_doc("School Group", school_group_id)
        except Exception:
            continue
            
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
                    try:
                        client.add_contact_to_group(glific_group_id, contact_id)
                        processed += 1
                    except GlificAPIError as e:
                        # Ignore "already exists" style errors to prevent retry pollution
                        err_str = str(e).lower()
                        if "duplicate" not in err_str and "already" not in err_str and "exists" not in err_str:
                            frappe.logger("tap_buddy_sync").error(f"Failed to add {school.name} to group {school_group_id}: {str(e)}")
                            
            except GlificAPIError as e:
                frappe.logger("tap_buddy_sync").error(f"Failed to upsert member {school.name} for group {school_group_id}: {str(e)}")

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
    if isinstance(response, list) and response:
        first = response[0]
        if isinstance(first, dict) and "id" in first:
            return first.get("id")
    return None


def _extract_group_id(response):
    if not response:
        return None
    if isinstance(response, dict):
        if "id" in response:
            return response.get("id")
        if "data" in response and isinstance(response["data"], dict):
            return response["data"].get("id")
        if "group" in response and isinstance(response["group"], dict):
            return response["group"].get("id")
    return None


def _max_datetime(current, candidate):
    if not candidate:
        return current
    if not current:
        return candidate
    return candidate if candidate > current else current
