import frappe

from tap_buddy.utils.constants import REC_STATUS_PENDING


def build_campaign_recipients(campaign_name: str) -> int:
    campaign = frappe.get_doc("TAP Campaign", campaign_name)
    targeting_type = campaign.targeting_type or "Single School"
    
    created = 0
    if targeting_type in ("Single School", "School Group"):
        schools = _resolve_target_schools(campaign)
        if not schools:
            return 0

        existing_rows = frappe.get_all(
            "Campaign Recipient",
            filters={"campaign": campaign.name, "school": ["in", schools]},
            fields=["school"],
        )
        existing = {row.school for row in existing_rows}

        for school in schools:
            if school in existing:
                continue
            recipient = frappe.new_doc("Campaign Recipient")
            recipient.campaign = campaign.name  # type: ignore[attr-defined]
            recipient.school = school  # type: ignore[attr-defined]
            recipient.status = REC_STATUS_PENDING  # type: ignore[attr-defined]
            recipient.scheduled_time = campaign.send_date  # type: ignore[attr-defined]
            recipient.insert(ignore_permissions=True)
            created += 1

    elif targeting_type in ("WhatsApp Group Collection", "WhatsApp Group"):
        groups = _resolve_target_wa_groups(campaign)
        if not groups:
            return 0

        existing_rows = frappe.get_all(
            "Campaign Recipient",
            filters={"campaign": campaign.name, "whatsapp_group": ["in", groups]},
            fields=["whatsapp_group"],
        )
        existing = {row.whatsapp_group for row in existing_rows}

        for group in groups:
            if group in existing:
                continue
            recipient = frappe.new_doc("Campaign Recipient")
            recipient.campaign = campaign.name  # type: ignore[attr-defined]
            recipient.whatsapp_group = group  # type: ignore[attr-defined]
            recipient.status = REC_STATUS_PENDING  # type: ignore[attr-defined]
            recipient.scheduled_time = campaign.send_date  # type: ignore[attr-defined]
            recipient.insert(ignore_permissions=True)
            created += 1

    return created


def get_recipient_context(school_name: str) -> dict:
    if not school_name:
        return {}
    school = frappe.get_doc("School", school_name)
    return {
        "school_name": school.school_name,  # type: ignore[attr-defined]
        "principal_name": school.principal_name,  # type: ignore[attr-defined]
        "district": school.district,  # type: ignore[attr-defined]
        "state": school.state,  # type: ignore[attr-defined]
        "block": school.block,  # type: ignore[attr-defined]
        "udise_code": school.udise_code,  # type: ignore[attr-defined]
    }


def _resolve_target_schools(campaign) -> list[str]:
    targeting_type = campaign.targeting_type or "Single School"

    if targeting_type == "School Group" and campaign.school_group:
        group = frappe.get_doc("School Group", campaign.school_group)
        schools = group.get_active_schools()
        return [s for s in schools if s]

    if campaign.school_name:
        return [campaign.school_name]

    return []

def _resolve_target_wa_groups(campaign) -> list[str]:
    targeting_type = campaign.targeting_type

    if targeting_type == "WhatsApp Group Collection" and campaign.target_collection:
        mappings = frappe.get_all(
            "WhatsApp Group Collection Mapping",
            filters={"collection": campaign.target_collection},
            fields=["whatsapp_group"]
        )
        return [m.whatsapp_group for m in mappings if m.whatsapp_group]

    if targeting_type == "WhatsApp Group" and campaign.target_group:
        return [campaign.target_group]

    return []
