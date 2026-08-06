"""
Probe the correct importFlow schema.
Usage: bench --site tapbuddy.local execute tap_buddy.probe_import_flow.run
"""
import frappe
import json


def run():
    from tap_buddy.services.glific_client import GlificClient
    client = GlificClient()

    # Probe 1: Find the correct return shape for importFlow status
    print("=== Probe: importFlow status subfield ===")
    try:
        res = client._graphql_request("""
        mutation importFlow($flow: Json!) {
          importFlow(flow: $flow) {
            status {
              flowName
              status
              isValid
            }
          }
        }
        """, {"flow": {"flows": [{"definition": {"uuid": "29597896-17d1-407a-8d11-a05b16dd4250", "nodes": []}}]}})
        print(json.dumps(res, indent=2)[:600])
    except Exception as e:
        print(f"Error: {e}")

    # Probe 2: What fields does importFlow accept?
    print("\n=== Probe: minimal importFlow ===")
    try:
        res = client._graphql_request("""
        mutation importFlow($flow: Json!) {
          importFlow(flow: $flow) {
            status { flowName status isValid }
          }
        }
        """, {"flow": {}})
        print(json.dumps(res, indent=2)[:600])
    except Exception as e:
        print(f"Error: {e}")

    # Probe 3: Try publishFlow or saveFlow
    print("\n=== Probe: publishFlow ===")
    try:
        res = client._graphql_request("""
        mutation publishFlow($uuid: UUID4!) {
          publishFlow(uuid: $uuid) {
            flow { id name uuid }
            errors { key message }
          }
        }
        """, {"uuid": "29597896-17d1-407a-8d11-a05b16dd4250"})
        print(json.dumps(res, indent=2)[:600])
    except Exception as e:
        print(f"publishFlow error: {e}")

    # Probe 4: Try getting flow definition via different route
    print("\n=== Probe: flows with definition ===")
    try:
        res = client._graphql_request("""
        query flows($filter: FlowFilter, $opts: Opts) {
          flows(filter: $filter, opts: $opts) {
            id name uuid
            keywords
          }
        }
        """, {"filter": {"name": "PRD_Awareness_Flow"}, "opts": {"limit": 5}})
        print(json.dumps(res, indent=2)[:600])
    except Exception as e:
        print(f"Error: {e}")
