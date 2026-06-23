import frappe
from tap_buddy.tasks.scheduler import dispatch_campaign
from tap_buddy.services.glific_client import GlificClient
import datetime
import json

def run():
    # Setup state
    frappe.cache().set_value("mock_glific", 0)
    
    # Bypass circuit breaker if any
    original_get_value = frappe.cache().get_value
    def mock_get_value(key, *args, **kwargs):
        if key == "glific_circuit_breaker":
            return False
        return original_get_value(key, *args, **kwargs)
    frappe.cache().get_value = mock_get_value

    # Monkey patch GraphQL to capture it
    original_request = GlificClient._graphql_request
    
    captured_requests = []
    
    def mocked_graphql(self, query, variables=None):
        if "sendMessageInWaGroup" in query:
            req_data = {
                "mutation": query,
                "variables": variables
            }
            captured_requests.append(req_data)
            try:
                res = original_request(self, query, variables)
                req_data["response"] = res
                return res
            except Exception as e:
                req_data["error"] = str(e)
                raise e
        return original_request(self, query, variables)
        
    GlificClient._graphql_request = mocked_graphql

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    msg_content = f"DIRECT GROUP MESSAGE TEST FROM TAP BUDDY\nTimestamp: {timestamp}"

    print(f"\n=== 1. Campaign Created ===")
    try:
        tmpl = frappe.get_doc({
            "doctype": "WhatsApp Template",
            "template_name": f"Test_Template_{int(frappe.utils.now_datetime().timestamp())}",
            "message": msg_content,
            "status": "Approved"
        })
        tmpl.insert(ignore_permissions=True)
        frappe.db.commit()

        # Create Campaign
        doc = frappe.get_doc({
            "doctype": "TAP Campaign",
            "campaign_name": f"Direct_Test_{int(frappe.utils.now_datetime().timestamp())}",
            "campaign_type": "Template",
            "targeting_type": "WhatsApp Group",
            "target_group": "WAG-12125",
            "template": tmpl.name,
            "message_template": msg_content,
            "status": "Scheduled",
            "send_date": frappe.utils.now_datetime()
        })
        doc.flags.ignore_mandatory = True
        doc.insert(ignore_permissions=True)
        frappe.db.commit()
        
        print(f"Campaign ID: {doc.name}")
        print(f"Target Group: {doc.target_group}")
        print(f"Message: {doc.message_template}")

        # Dispatch the campaign
        dispatch_campaign(doc.name)
        frappe.db.commit()
    except Exception as e:
        print(f"Error during creation/dispatch: {e}")

    # Confirm recipient creation
    print(f"\n=== 2. Campaign Recipient ===")
    try:
        recipients = frappe.get_all("Campaign Recipient", filters={"campaign": doc.name}, fields=["name", "whatsapp_group", "status", "failure_reason"])
        for r in recipients:
            print(json.dumps(r, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # GraphQL Output
    print(f"\n=== 3. GraphQL Mutation Sent ===")
    if captured_requests:
        req = captured_requests[0]
        print(req["mutation"].strip())
        print("\nVariables:")
        print(json.dumps(req.get("variables"), indent=2))
        
        print(f"\n=== 4. GraphQL Response ===")
        if "response" in req:
            print(json.dumps(req.get("response"), indent=2))
        elif "error" in req:
            print(f"Error: {req['error']}")
    else:
        print("No sendMessageInWaGroup mutation captured.")

    # Capture Dispatch Attempt
    print(f"\n=== 5. Dispatch Attempt ===")
    try:
        attempts = frappe.get_all("Dispatch Attempt", filters={"campaign": doc.name}, fields=["name", "recipient", "status", "whatsapp_group", "provider_message_id", "error_message"])
        for a in attempts:
            print(json.dumps(a, indent=2))
            
            doc_attempt = frappe.get_doc("Dispatch Attempt", a["name"])
            print("API Response:", doc_attempt.api_response)
    except Exception as e:
        print(f"Error: {e}")

    # Log Entries
    print(f"\n=== 6. Log Entries (from database) ===")
    try:
        logs = frappe.get_all("Error Log", filters={"method": ["like", f"%{doc.name}%"]}, limit=5)
        if logs:
            for l in logs:
                print(f"Error Log: {l.name}")
        else:
            print("No Error Logs.")
    except Exception as e:
        print(f"Error: {e}")

    # Restore
    GlificClient._graphql_request = original_request
