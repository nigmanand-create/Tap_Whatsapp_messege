import frappe
from frappe.utils import now_datetime

def test_zombie_campaign():
    frappe.init(site="tapbuddy.local")
    frappe.connect()
    
    frappe.db.sql("DELETE FROM `tabLMS Student`")
    frappe.db.sql("DELETE FROM `tabTAP Campaign`")
    frappe.db.sql("DELETE FROM `tabCampaign Recipient`")
    frappe.db.sql("DELETE FROM `tabSchool Group`")
    frappe.db.sql("DELETE FROM `tabSchool`")
    frappe.db.commit()

    if not frappe.db.exists("WhatsApp Template", "test_template"):
        frappe.get_doc({
            "doctype": "WhatsApp Template",
            "template_name": "test_template",
            "message": "Hello",
            "language": "English"
        }).insert(ignore_permissions=True)

    # Create an INACTIVE school
    frappe.get_doc({
        "doctype": "School",
        "school_name": "Inactive School",
        "lms_school_status": "Inactive"
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    # Create a school group with the inactive school
    group = frappe.get_doc({
        "doctype": "School Group",
        "group_name": "Inactive Group",
        "is_active": 0,
        "members": [{"school": "Inactive School"}]
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    # Create campaign
    campaign = frappe.get_doc({
        "doctype": "TAP Campaign",
        "campaign_name": "Test Zombie",
        "targeting_type": "School Group",
        "school_group": "Inactive Group",
        "template": "test_template",
        "message_template": "Hello",
        "send_date": now_datetime(),
        "status": "Queued"
    }).insert(ignore_permissions=True)
    frappe.db.commit()

    print(f"Initial Status: {campaign.status}")

    # Dispatch it!
    from tap_buddy.tasks.scheduler import dispatch_campaign, sync_campaign_counts
    dispatch_campaign(campaign.name)
    frappe.db.commit()
    
    campaign.reload()
    total_recipients = frappe.db.count("Campaign Recipient", {"campaign": campaign.name})
    print(f"After Dispatch: Status={campaign.status}, Recipients={total_recipients}")
    
    # Try syncing counts
    sync_campaign_counts()
    campaign.reload()
    print(f"After Sync Counts: Status={campaign.status}")

if __name__ == "__main__":
    test_zombie_campaign()
