import frappe
def run():
    campaigns = frappe.get_all("TAP Campaign", filters={"campaign_name": ("like", "E2E%")}, fields=["name", "status", "send_date"])
    for c in campaigns:
        print(f"Campaign: {c.name}, Status: {c.status}, send_date: {c.send_date}")
        recs = frappe.get_all("Campaign Recipient", filters={"campaign": c.name}, fields=["name", "status", "school"])
        print("  Recipients:", recs)
