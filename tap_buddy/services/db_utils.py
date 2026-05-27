import frappe

def get_pending_recipients_for_update(campaign_name, limit=50):
    """
    Safely fetches and locks a batch of pending recipients using FOR UPDATE SKIP LOCKED.
    Returns a list of recipient names that were successfully locked.
    """
    if frappe.db.db_type == "postgres":
        rows = frappe.db.sql(
            """
            SELECT name FROM "tabCampaign Recipient" 
            WHERE campaign = %s AND status = 'Pending' 
            LIMIT %s FOR UPDATE SKIP LOCKED
            """,
            (campaign_name, limit),
            as_dict=True
        )
    else:
        rows = frappe.db.sql(
            """
            SELECT name FROM `tabCampaign Recipient` 
            WHERE campaign = %s AND status = 'Pending' 
            LIMIT %s FOR UPDATE SKIP LOCKED
            """,
            (campaign_name, limit),
            as_dict=True
        )
        
    return [row.name for row in rows] if rows else []

def get_failed_recipients_for_update(campaign_names, limit=50, max_retries=3):
    """
    Safely fetches and locks a batch of failed recipients eligible for retry using FOR UPDATE SKIP LOCKED.
    """
    if not campaign_names:
        return []
        
    format_str = ", ".join(["%s"] * len(campaign_names))
    params = list(campaign_names) + [max_retries, limit]
    
    if frappe.db.db_type == "postgres":
        query = f"""
            SELECT name FROM "tabCampaign Recipient"
            WHERE campaign IN ({format_str})
            AND status = 'Failed'
            AND terminal_failure = 0
            AND retry_count < %s
            ORDER BY modified ASC
            LIMIT %s FOR UPDATE SKIP LOCKED
        """
    else:
        query = f"""
            SELECT name FROM `tabCampaign Recipient`
            WHERE campaign IN ({format_str})
            AND status = 'Failed'
            AND terminal_failure = 0
            AND retry_count < %s
            ORDER BY modified ASC
            LIMIT %s FOR UPDATE SKIP LOCKED
        """
        
    rows = frappe.db.sql(query, params, as_dict=True)
    return [row.name for row in rows] if rows else []

def mark_recipients_processing(recipient_names):
    """
    Bulk update statuses to 'Processing'.
    """
    if not recipient_names:
        return
        
    format_str = ", ".join(["%s"] * len(recipient_names))
    params = ["Processing"] + list(recipient_names)
    
    if frappe.db.db_type == "postgres":
        frappe.db.sql(f"""
            UPDATE "tabCampaign Recipient"
            SET status = %s
            WHERE name IN ({format_str})
        """, params)
    else:
        frappe.db.sql(f"""
            UPDATE `tabCampaign Recipient`
            SET status = %s
            WHERE name IN ({format_str})
        """, params)
