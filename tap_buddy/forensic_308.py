import frappe

def run():
    frappe.db.rollback()
    
    print("\n--- Recent Campaigns ---")
    camps = frappe.get_all("TAP Campaign", fields=["name", "status", "glific_flow"], filters={"name": ["in", ["TAP-2026-00308", "TAP-2026-00309", "TAP-2026-00310"]]}, order_by="name asc")
    for c in camps:
        print(c)
