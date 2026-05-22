import frappe
from frappe.utils import now_datetime


def handle_lms_event(log, payload):
    mapping = _get_mapping(log.event_type)
    if not mapping:
        return {"status": "Skipped", "error": "No mapping for event_type"}

    if mapping.action == "Log Only":
        return {"status": "Processed", "mapping": mapping.name}

    if mapping.action != "Create Campaign":
        return {"status": "Failed", "error": "Unsupported mapping action", "mapping": mapping.name}

    campaign = _create_campaign(mapping, payload)
    if not campaign:
        return {"status": "Failed", "error": "Failed to create campaign", "mapping": mapping.name}

    return {"status": "Processed", "mapping": mapping.name, "campaign": campaign}


def _get_mapping(event_type):
    rows = frappe.get_all(
        "LMS Event Mapping",
        filters={"event_type": event_type, "enabled": 1},
        fields=["name"],
        limit=1,
    )
    if not rows:
        return None
    return frappe.get_doc("LMS Event Mapping", rows[0].name)


def _create_campaign(mapping, payload):
    template_name, message_template = _resolve_template(mapping)
    if not template_name or not message_template:
        return None

    campaign = frappe.new_doc("TAP Campaign")
    campaign.campaign_name = _build_campaign_name(mapping, payload)
    campaign.template = template_name
    campaign.message_template = message_template
    campaign.send_date = now_datetime()

    targeting_type = mapping.targeting_type or "Single School"
    campaign.targeting_type = targeting_type

    if targeting_type == "Single School":
        school_name = _read_payload_value(payload, mapping.school_name_key) or _read_payload_value(payload, "school_name")
        if not school_name:
            return None
        school = frappe.get_value("School", {"school_name": school_name}, "name")
        if not school:
            return None
        campaign.school_name = school
    else:
        school_group = _read_payload_value(payload, mapping.school_group_key) or _read_payload_value(payload, "school_group")
        if not school_group:
            return None
        group = frappe.get_value("School Group", {"group_name": school_group}, "name")
        if not group:
            return None
        campaign.school_group = group

    campaign.insert(ignore_permissions=True)
    return campaign.name


def _build_campaign_name(mapping, payload):
    prefix = mapping.campaign_name_prefix or "LMS"
    event_id = _read_payload_value(payload, "event_id") or _read_payload_value(payload, "id")
    suffix = event_id or now_datetime().strftime("%Y%m%d%H%M%S")
    return f"{prefix} {suffix}"


def _resolve_template(mapping):
    if not mapping.template:
        return None, None
    message = mapping.message_template_override
    if not message:
        message = frappe.get_value("WhatsApp Template", mapping.template, "message")
    return mapping.template, message


def _read_payload_value(payload, key_path):
    if not key_path:
        return None
    if not isinstance(payload, dict):
        return None
    if key_path in payload:
        return payload.get(key_path)

    if "." in key_path:
        current = payload
        for part in key_path.split("."):
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        return current

    if "data" in payload and isinstance(payload["data"], dict):
        return payload["data"].get(key_path)

    return None
