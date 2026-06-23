import frappe
import json

def run():
    frappe.db.rollback()
    
    print("\n--- Recent Campaigns ---")
    camps = frappe.get_all("TAP Campaign", fields=["name", "status", "glific_flow"], limit=5, order_by="creation desc")
    for c in camps:
        print(c)
        
    print("\n--- Recent Recipients ---")
    recs = frappe.get_all("Campaign Recipient", fields=["name", "campaign", "status", "failure_reason"], limit=5, order_by="creation desc")
    for r in recs:
        print(r)
        
    print("\n--- Recent Dispatch Attempts ---")
    attempts = frappe.get_all("Dispatch Attempt", fields=["name", "recipient", "status", "error_message"], limit=5, order_by="creation desc")
    for a in attempts:
        print(a)
