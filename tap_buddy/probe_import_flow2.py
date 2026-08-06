"""
Continue probing importFlow and publishFlow correct shapes.
Usage: bench --site tapbuddy.local execute tap_buddy.probe_import_flow2.run
"""
import frappe
import json


def run():
    from tap_buddy.services.glific_client import GlificClient
    client = GlificClient()

    # Probe 1: importFlow with status subfields (no isValid)
    print("=== Probe: importFlow status { flowName status } ===")
    try:
        res = client._graphql_request("""
        mutation importFlow($flow: Json!) {
          importFlow(flow: $flow) {
            status { flowName status }
          }
        }
        """, {"flow": {}})
        print(json.dumps(res, indent=2)[:800])
    except Exception as e:
        print(f"Error: {e}")

    # Probe 2: publishFlow correct return shape
    print("\n=== Probe: publishFlow correct return ===")
    try:
        res = client._graphql_request("""
        mutation publishFlow($uuid: UUID4!) {
          publishFlow(uuid: $uuid) {
            status
            errors { key message }
          }
        }
        """, {"uuid": "29597896-17d1-407a-8d11-a05b16dd4250"})
        print(json.dumps(res, indent=2)[:600])
    except Exception as e:
        print(f"publishFlow error: {e}")

    # Probe 3: Can we use exportFlow to get UUID and then updateFlow with flow definition?
    print("\n=== Probe: updateFlow with definition fields ===")
    try:
        res = client._graphql_request("""
        mutation updateFlow($id: ID!, $input: FlowInput!) {
          updateFlow(id: $id, input: $input) {
            flow { id name uuid isActive }
            errors { key message }
          }
        }
        """, {
            "id": "40764",
            "input": {
                "name": "PRD_Awareness_Flow",
                "keywords": ["awareness"]
            }
        })
        print(json.dumps(res, indent=2)[:600])
    except Exception as e:
        print(f"updateFlow error: {e}")

    # Probe 4: Find Glific REST endpoint for flow import
    print("\n=== Probe: Check Glific API base URL ===")
    settings = frappe.get_single("TAP Buddy Settings")
    print(f"Glific URL: {settings.get('glific_url', 'N/A')}")
