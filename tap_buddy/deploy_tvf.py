import frappe
from tap_buddy.services.bigquery_executor import get_bq_client
import os

def run():
    client = get_bq_client()
    tvf_path = frappe.get_app_path("tap_buddy", "sql", "tvfs", "get_registration_analytics_context_v1.sql")
    with open(tvf_path, 'r') as f:
        sql = f.read()
    
    print("Deploying TVF to BigQuery...")
    job = client.query(sql)
    job.result()  # Wait for the job to complete
    print("TVF deployed successfully!")
