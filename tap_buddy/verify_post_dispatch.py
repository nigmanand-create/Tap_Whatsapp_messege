import frappe
import json
from tap_buddy.services.glific_client import GlificClient

def run():
    frappe.cache().set_value("mock_glific", 0)
    client = GlificClient()

    print("\n=== 1. Verify Flow Definition ===")
    query_flow = """
    query {
      flow(id: 40067) {
        flow {
          id
          name
          isActive
        }
      }
    }
    """
    try:
        res = client._graphql_request(query_flow, {})
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    print("\n=== 5. Verify Collection Membership ===")
    query_group = """
    query {
      group(id: 20996) {
        group {
          id
          label
          contactsCount
          usersCount
          waGroupsCount
          waGroups {
            id
            name
          }
        }
      }
    }
    """
    try:
        res = client._graphql_request(query_group, {})
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    print("\n=== 6. Verify WhatsApp Group Linkage ===")
    query_wag = """
    query {
      group(id: 12125) {
        group {
          id
          label
          contactsCount
          usersCount
          waGroupsCount
        }
      }
    }
    """
    try:
        res = client._graphql_request(query_wag, {})
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error: {e}")
