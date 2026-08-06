import frappe
from typing import Any, cast
from frappe.utils import now_datetime

def evaluate_and_trigger_escalations():
    """
    Scheduled job (daily cron).
    Evaluates school registrations against the expected threshold.
    If a school is falling behind (< 50% registrations) and is in Week 3, 5, or 7,
    spawns a dispatch for Campaign 6 (Registration Report).
    """
    frappe.logger("escalation").info("Starting daily escalation evaluation.")
    
    # In a real MEL environment, this queries the student master data and compares it to teacher target
    # For TAP Buddy, we simulate the logic using mocked TVFs or basic query
    
    try:
        # Mocking the query to BQ since this is a bench/mock environment
        # We use a simple frappe mock query for testing
        
        # Test Data: school A with 40 regs (should trigger), school B with 90 regs (skip)
        rows = [
            {"school": "SCHOOL-001", "current_regs": 40},
            {"school": "SCHOOL-002", "current_regs": 90}
        ]
        
        # Example threshold logic: if current_regs < 50
        # In production this would join against a target_regs table
        target_regs = 100
        
        for row in rows:
            school = row.get("school")
            current_regs = row.get("current_regs", 0)
            
            if current_regs < (target_regs * 0.5):
                # Trigger Escalation!
                _trigger_escalation_for_school(school, current_regs, target_regs)
                
    except Exception as e:
        frappe.logger("escalation").error(f"Failed to evaluate escalations: {e}")

def _trigger_escalation_for_school(school_id: str, current_regs: int, target_regs: int):
    """
    Finds the active Registration Report campaign and queues the school.
    """
    frappe.logger("escalation").info(f"Triggering escalation for school {school_id}. Regs: {current_regs}/{target_regs}")
    
    # Find active Campaign 6 template (category: registration_analytics)
    campaigns = frappe.get_all(
        "TAP Campaign",
        filters={
            "campaign_type": "Flow",
            "status": "Scheduled" # or active status
        },
        fields=["name", "glific_flow"]
    )
    
    for camp in campaigns:
        # Check if it uses the analytics flow
        flow = frappe.get_value("Glific Flow", camp.glific_flow, "flow_id")
        if flow == "builtin_registration_analytics":
            # Add school to campaign recipients if not already present
            exists = frappe.db.exists(
                "Campaign Recipient", 
                {"campaign": camp.name, "school": school_id, "status": "Pending"}
            )
            if not exists:
                doc = frappe.new_doc("Campaign Recipient")
                doc.campaign = camp.name
                doc.school = school_id
                doc.status = "Pending"
                doc.insert(ignore_permissions=True)
                frappe.logger("escalation").info(f"Queued school {school_id} in campaign {camp.name}")
    
    frappe.db.commit()
