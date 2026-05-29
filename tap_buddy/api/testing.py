import frappe

@frappe.whitelist(allow_guest=True)
def reset_cb():
    frappe.cache().delete_value("tap_buddy:cb:glific")
    frappe.cache().delete_value("tap_buddy:cb:lms")
    return {"status": 200, "message": "Circuit breakers reset"}

@frappe.whitelist(allow_guest=True)
def process_webhook_queue():
    from tap_buddy.services.webhook_processor import process_webhook_batches
    return process_webhook_batches()

@frappe.whitelist()
def set_webhook_settings(webhook_secret: str, webhook_enabled: int):
    """Safely update webhook settings without triggering password masking bugs."""
    if not frappe.session.user == "Administrator":
        frappe.throw("Not permitted", frappe.PermissionError)
    
    frappe.db.set_value("TAP Buddy Settings", "TAP Buddy Settings", "webhook_secret", webhook_secret)
    frappe.db.set_value("TAP Buddy Settings", "TAP Buddy Settings", "webhook_enabled", webhook_enabled)
    frappe.db.commit()
    
    return {"status": 200, "message": "Webhook settings updated safely"}

@frappe.whitelist()
def set_lms_settings(webhook_secret: str, enabled: int):
    """Safely update LMS settings without triggering password masking bugs."""
    if not frappe.session.user == "Administrator":
        frappe.throw("Not permitted", frappe.PermissionError)
    
    frappe.db.set_value("LMS Integration Settings", "LMS Integration Settings", "webhook_secret", webhook_secret)
    frappe.db.set_value("LMS Integration Settings", "LMS Integration Settings", "enabled", enabled)
    frappe.db.commit()
    
    return {"status": 200, "message": "LMS settings updated safely"}

@frappe.whitelist()
def set_mock_glific(is_mock: int):
    """Enable or disable Glific API mocking for E2E tests."""
    frappe.cache().set_value("mock_glific", is_mock)
    return {"status": 200, "message": f"Glific mock set to {is_mock}"}
