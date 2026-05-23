"""Recipient creation helpers for TAP Buddy campaigns."""

from __future__ import annotations

import frappe


def build_campaign_recipients(campaign_name: str) -> int:
    """Create a recipient snapshot for the campaign's target school.

    The current implementation is intentionally narrow: it creates a single
    Campaign Recipient row for the campaign's linked school when one does not
    already exist. This is enough to make campaign submission durable and to
    exercise the dispatch pipeline without guessing at a larger audience model.
    """
    campaign = frappe.get_doc("TAP Campaign", campaign_name)
    school_name = getattr(campaign, "school_name", None)
    if not school_name:
        return 0

    existing = frappe.db.exists(
        "Campaign Recipient",
        {
            "campaign": campaign.name,
            "school": school_name,
        },
    )
    if existing:
        return 0

    recipient = frappe.get_doc(
        {
            "doctype": "Campaign Recipient",
            "campaign": campaign.name,
            "school": school_name,
            "status": "Pending",
        }
    )
    recipient.insert(ignore_permissions=True)
    return 1
