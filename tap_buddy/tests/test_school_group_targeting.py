import frappe
import pytest
from tap_buddy.services.recipients import build_campaign_recipients

def setup_module(module):
    frappe.init(site="tapbuddy.local")
    frappe.connect()

    # Create dummy schools
    for i in range(1, 3):
        if not frappe.db.exists("School", f"TEST-SCH-TAR-{i}"):
            frappe.get_doc({
                "doctype": "School",
                "school_name": f"TEST-SCH-TAR-{i}",
                "whatsapp_number": f"+91-999999999{i}",
                "is_active": 1
            }).insert(ignore_permissions=True)
            
    # Ensure a template exists
    if not frappe.db.exists("WhatsApp Template", "Test Target Template"):
        frappe.get_doc({
            "doctype": "WhatsApp Template",
            "template_name": "Test Target Template",
            "message": "Hello"
        }).insert(ignore_permissions=True)


def create_group(name, is_active):
    if not frappe.db.exists("School Group", name):
        doc = frappe.get_doc({
            "doctype": "School Group",
            "group_name": name,
            "is_active": is_active,
            "members": [
                {"school": "TEST-SCH-TAR-1"},
                {"school": "TEST-SCH-TAR-2"}
            ]
        }).insert(ignore_permissions=True)
    else:
        doc = frappe.get_doc("School Group", name)
        doc.is_active = is_active
        doc.save(ignore_permissions=True)
    return doc


def create_campaign(camp_name, group_name):
    frappe.db.sql("DELETE FROM `tabTAP Campaign` WHERE name = %s", camp_name)
    frappe.db.sql("DELETE FROM `tabCampaign Recipient` WHERE campaign = %s", camp_name)

    frappe.db.sql("""
        INSERT INTO `tabTAP Campaign` (name, campaign_name, status, send_date, targeting_type, school_group, template)
        VALUES (%s, %s, 'Queued', '2020-01-01 10:00:00', 'School Group', %s, 'Test Target Template')
    """, (camp_name, camp_name, group_name))
    frappe.db.commit()


def test_active_group_creates_recipients():
    """Scenario A & C: Active group members exist, recipients created, existing behaviour unchanged."""
    create_group("TEST-ACTIVE-GROUP", is_active=1)
    create_campaign("TEST-CAMP-ACTIVE", "TEST-ACTIVE-GROUP")
    
    created = build_campaign_recipients("TEST-CAMP-ACTIVE")
    group_test = frappe.get_doc("School Group", "TEST-ACTIVE-GROUP")
    print(f"\n[DEBUG] Group {group_test.name} is_active: {group_test.is_active}")
    print(f"[DEBUG] Group {group_test.name} members: {[m.school for m in group_test.members]}")
    print(f"[DEBUG] Group {group_test.name} active_schools: {group_test.get_active_schools()}")
    assert created == 2, f"Expected 2 recipients for active group, got {created}"
    
    recipients = frappe.get_all("Campaign Recipient", filters={"campaign": "TEST-CAMP-ACTIVE"})
    assert len(recipients) == 2


def test_inactive_group_creates_zero_recipients():
    """Scenario B: Inactive group members exist, zero recipients created."""
    create_group("TEST-INACTIVE-GROUP", is_active=0)
    create_campaign("TEST-CAMP-INACTIVE", "TEST-INACTIVE-GROUP")
    
    created = build_campaign_recipients("TEST-CAMP-INACTIVE")
    assert created == 0, f"Expected 0 recipients for inactive group, got {created}"
    
    recipients = frappe.get_all("Campaign Recipient", filters={"campaign": "TEST-CAMP-INACTIVE"})
    assert len(recipients) == 0

    # Cleanup
    frappe.db.sql("DELETE FROM `tabTAP Campaign` WHERE name IN ('TEST-CAMP-ACTIVE', 'TEST-CAMP-INACTIVE')")
    frappe.db.commit()
