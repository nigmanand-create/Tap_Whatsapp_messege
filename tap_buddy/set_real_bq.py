import frappe
def run():
    bq_settings = frappe.get_single("TAP BigQuery Settings")
    bq_settings.project_id = "central-phalanx-297915"
    bq_settings.dataset_id = "MEL_datasets"
    bq_settings.service_account_json = "/Users/blackstar/Downloads/central-phalanx-297915-78012c855a38.json"
    bq_settings.enabled = 1
    bq_settings.save(ignore_permissions=True)
    frappe.db.commit()
    print("Real BigQuery credentials configured.")
