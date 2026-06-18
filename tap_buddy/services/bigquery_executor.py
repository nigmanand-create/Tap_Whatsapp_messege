import json
import re
import hashlib
import datetime
import decimal
import frappe
from google.cloud import bigquery
from google.oauth2 import service_account

# Regex to allow only alphanumeric and underscore for TVF resource names
RESOURCE_NAME_REGEX = re.compile(r"^[a-zA-Z0-9_]+$")

class JSONEncoderCustom(json.JSONEncoder):
    """Custom JSON encoder to handle BigQuery native types like datetime, date, and Decimal."""
    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        if isinstance(obj, decimal.Decimal):
            return float(obj)
        return super().default(obj)

def get_bq_client(mock_mode=False):
    if mock_mode:
        return None
    
    settings = frappe.get_single("TAP BigQuery Settings")
    if not settings.enabled:
        frappe.throw("BigQuery integration is disabled.", exc=frappe.exceptions.ValidationError)
        
    sa_json_str = settings.get_password("service_account_json")
    if not sa_json_str:
        frappe.throw("Service Account JSON is missing.", exc=frappe.exceptions.ValidationError)
        
    try:
        sa_info = json.loads(sa_json_str)
    except json.JSONDecodeError as e:
        frappe.throw(f"Invalid Service Account JSON: {str(e)}", exc=frappe.exceptions.ValidationError)
        
    credentials = service_account.Credentials.from_service_account_info(sa_info)
    return bigquery.Client(credentials=credentials, project=settings.project_id)

def execute_tvf(resource, parameters, mock_mode=False):
    """
    Executes a BigQuery Table Valued Function passing the parameters as a single JSON string.
    """
    if not RESOURCE_NAME_REGEX.match(resource):
        frappe.throw("Invalid resource name format.", exc=frappe.exceptions.ValidationError)
        
    settings = frappe.get_single("TAP BigQuery Settings")
    project_id = settings.project_id
    dataset_id = settings.dataset_id
    
    if not project_id or not dataset_id:
        frappe.throw("Project ID or Dataset ID is not configured.", exc=frappe.exceptions.ValidationError)

    json_payload_str = json.dumps(parameters)
    
    if mock_mode:
        # Return a mocked row iterator equivalent for unit testing
        return [{"mocked": True, "resource": resource, "payload": json_payload_str}]

    client = get_bq_client(mock_mode=False)
    
    # TVF invocation syntax: SELECT * FROM `project.dataset.routine`(@json_payload)
    query = f"SELECT * FROM `{project_id}.{dataset_id}.{resource}`(@json_payload)"
    
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("json_payload", "STRING", json_payload_str)
        ]
    )
    
    try:
        start_time = datetime.datetime.now()
        query_job = client.query(query, job_config=job_config)
        rows = query_job.result()  # Waits for job to complete.
        duration = (datetime.datetime.now() - start_time).total_seconds()
        
        frappe.logger("bigquery").info(f"[BigQuery Executor] Executed {resource} in {duration:.3f}s")
        
        # Extract rows
        return [dict(row) for row in rows]
        
    except Exception as e:
        frappe.logger("bigquery").error(f"[BigQuery Executor] Failure on {resource}: {str(e)}")
        raise
