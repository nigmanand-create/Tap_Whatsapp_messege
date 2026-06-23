import frappe
import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()

    print("\n=== 1 & 2 & 3. Verifying waGroupId 12125 ===")
    query_wagroup = """
    query {
      waGroup(id: 12125) {
        waGroup {
          id
          label
          bspId
          lastCommunicationAt
          phones {
            id
            phone
          }
        }
      }
    }
    """
    try:
        res = client._graphql_request(query_wagroup, {})
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error fetching waGroup: {e}")
        
    print("\n=== Fetching Error Logs ===")
    query_logs = """
    query {
      errorLogs(opts: {limit: 5}) {
        id
        error
        status
        stacktrace
        insertedAt
      }
    }
    """
    try:
        res = client._graphql_request(query_logs, {})
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error fetching errorLogs: {e}")

    print("\n=== 4 & 5. Executing sendMessageInWaGroup ===")
    query_mutation = """
    mutation sendMessageInWaGroup($input: WaMessageInput!) {
      sendMessageInWaGroup(input: $input) {
        errors {
          key
          message
        }
      }
    }
    """
    variables = {
        "input": {
            "waGroupId": "12125",
            "message": "DIRECT GLIFIC TEST",
            "type": "TEXT"
        }
    }
    
    print("Request:")
    print(query_mutation.strip())
    print("Variables:", json.dumps(variables, indent=2))
    
    try:
        res = client._graphql_request(query_mutation, variables)
        print("\nResponse:")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"\nException caught during mutation request: {e}")
