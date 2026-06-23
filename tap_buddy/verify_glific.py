import frappe
import json
from tap_buddy.services.glific_client import GlificClient

def run():
    frappe.cache().set_value("mock_glific", 0) # ensure we hit the real API
    client = GlificClient()
    
    print("\n--- Verifying Flow 40067 ---")
    query_flow = """
    query {
      flow(id: 40067) {
        id
        name
        status
        isActive
      }
    }
    """
    res_flow = client._graphql_request(query_flow, {})
    print(json.dumps(res_flow, indent=2))
    
    print("\n--- Verifying Group 12125 ---")
    query_group = """
    query {
      group(id: 12125) {
        id
        label
        isSystem
        status
      }
    }
    """
    res_group = client._graphql_request(query_group, {})
    print(json.dumps(res_group, indent=2))
    
    print("\n--- Verifying Collection 20996 ---")
    query_collection = """
    query {
      group(id: 20996) {
        id
        label
        isSystem
        status
      }
    }
    """
    res_collection = client._graphql_request(query_collection, {})
    print(json.dumps(res_collection, indent=2))
    
    # Check resolution if 12125 has 20996? Not sure if there is an API for mapping. The mapping is in TAP.
