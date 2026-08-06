import frappe
def run():
    settings = frappe.get_single("TAP BigQuery Settings")
    print(f"Enabled: {settings.enabled}")
    print(f"Project ID: {settings.project_id}")
    print(f"Dataset ID: {settings.dataset_id}")
    try:
        print(f"Secret: {settings.get_password('service_account_json')[:20]}...")
    except Exception as e:
        print(f"Secret not found: {e}")
