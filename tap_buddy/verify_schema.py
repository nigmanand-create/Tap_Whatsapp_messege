import frappe
import json
from tap_buddy.services.glific_client import GlificClient

def run():
    # bypass circuit breaker
    original_get_value = frappe.cache().get_value
    def mock_get_value(key, *args, **kwargs):
        if key == "glific_circuit_breaker":
            return False
        return original_get_value(key, *args, **kwargs)
    frappe.cache().get_value = mock_get_value
    
    frappe.cache().set_value("mock_glific", 0)
    client = GlificClient()

    query = """
    query {
      __type(name: "GroupResult") {
        fields {
          name
          type {
            name
            kind
          }
        }
      }
    }
    """
    res = client._graphql_request(query, {})
    print("GroupResult:", json.dumps(res, indent=2))
    
    query2 = """
    query {
      __type(name: "Group") {
        fields {
          name
        }
      }
    }
    """
    res2 = client._graphql_request(query2, {})
    print("Group:", json.dumps(res2, indent=2))
    
    query3 = """
    query {
      __type(name: "RootQueryType") {
        fields {
          name
          args { name }
          type { name kind }
        }
      }
    }
    """
    res3 = client._graphql_request(query3, {})
    fields = res3.get("data", {}).get("__type", {}).get("fields", [])
    for f in fields:
        if f["name"] in ["flow", "flows", "group", "groups", "messages", "flowRuns"]:
            print(f["name"], f["type"])
            
