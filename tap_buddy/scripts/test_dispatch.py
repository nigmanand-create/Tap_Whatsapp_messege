import frappe
from frappe.utils import get_datetime, now_datetime
from tap_buddy.tasks.scheduler import _is_within_dispatch_window

def run():
    campaign_name = "TAP-2026-00269"
    # Reset failed recipients to Pending
    frappe.db.sql("""
        UPDATE `tabCampaign Recipient`
        SET status = 'Pending', terminal_failure = 0, retry_count = 0
        WHERE campaign = %s
    """, (campaign_name,))
    frappe.db.commit()
    print("Recipients reset to Pending")
    
    # Run dispatch
    from tap_buddy.tasks.scheduler import dispatch_campaign, sync_campaign_counts
    dispatch_campaign(campaign_name)
    print("Dispatch completed")
    
    # Run sync
    sync_campaign_counts()
    print("Sync completed")

