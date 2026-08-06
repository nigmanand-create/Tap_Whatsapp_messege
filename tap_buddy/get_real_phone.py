import frappe
from tap_buddy.services.bigquery_executor import get_bq_client

def run():
    client = get_bq_client()
    query = """
        SELECT contact_phone 
        FROM `central-phalanx-297915.MEL_2025_26.tlm25_teacher_data_table` 
        WHERE contact_phone IS NOT NULL
        LIMIT 1
    """
    job = client.query(query)
    for row in job:
        print(f"Real Phone: {row['contact_phone']}")
