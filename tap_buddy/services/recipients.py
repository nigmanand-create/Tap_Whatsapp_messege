import frappe

from tap_buddy.utils.constants import REC_STATUS_PENDING


def build_campaign_recipients(campaign_name: str) -> int:
    campaign = frappe.get_doc("TAP Campaign", campaign_name)
    schools = _resolve_target_schools(campaign)
    if not schools:
        return 0

    existing_rows = frappe.get_all(
        "Campaign Recipient",
        filters={"campaign": campaign.name, "school": ["in", schools]},
        fields=["school"],
    )
    existing = {row.school for row in existing_rows}

    created = 0
    for school in schools:
        if school in existing:
            continue
        recipient = frappe.new_doc("Campaign Recipient")
        recipient.campaign = campaign.name
        recipient.school = school
        recipient.status = REC_STATUS_PENDING
        recipient.scheduled_time = campaign.send_date
        recipient.insert(ignore_permissions=True)
        created += 1

    return created


def get_recipient_context(school_name: str) -> dict:
    school = frappe.get_doc("School", school_name)
    return {
        "school_name": school.school_name,
        "principal_name": school.principal_name,
        "district": school.district,
        "state": school.state,
        "block": school.block,
        "udise_code": school.udise_code,
    }


def _resolve_target_schools(campaign) -> list[str]:
    targeting_type = campaign.targeting_type or "Single School"

    if targeting_type == "School Group" and campaign.school_group:
        group = frappe.get_doc("School Group", campaign.school_group)
        schools = group.get_active_schools() or [m.school for m in group.members]
        return [s for s in schools if s]

    if campaign.school_name:
        return [campaign.school_name]

    return []
