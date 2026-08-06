"""
Probe Glific GraphQL schema to find correct mutation for flow configuration.
Usage: bench --site tapbuddy.local execute tap_buddy.probe_glific_schema.run
"""
import frappe
import json


def run():
    from tap_buddy.services.glific_client import GlificClient
    client = GlificClient()

    # --- Probe 1: flow() query correct shape ---
    print("\n=== PROBE 1: flow() query shape ===")
    try:
        res = client._graphql_request("""
        query flow($id: ID!) {
          flow(id: $id) {
            flow {
              id name uuid flowType isActive
            }
            errors { key message }
          }
        }
        """, {"id": "40764"})
        print(json.dumps(res, indent=2, ensure_ascii=False)[:600])
    except Exception as e:
        print(f"flow() error: {e}")

    # --- Probe 2: exportFlow correct shape ---
    print("\n=== PROBE 2: exportFlow query shape ===")
    try:
        res = client._graphql_request("""
        query exportFlow($id: ID!) {
          exportFlow(id: $id) {
            export_data: exportData
            errors { key message }
          }
        }
        """, {"id": "40764"})
        print(json.dumps(res, indent=2, ensure_ascii=False)[:400])
    except Exception as e:
        print(f"exportFlow error: {e}")

    # --- Probe 3: What does importFlow accept? ---
    print("\n=== PROBE 3: importFlow mutation shape ===")
    try:
        res = client._graphql_request("""
        mutation importFlow($flow: Json!) {
          importFlow(flow: $flow) {
            flow { id name uuid }
            errors { key message }
          }
        }
        """, {"flow": {}})
        print(json.dumps(res, indent=2, ensure_ascii=False)[:400])
    except Exception as e:
        print(f"importFlow error: {e}")

    # --- Probe 4: updateFlow mutation ---
    print("\n=== PROBE 4: updateFlow mutation shape ===")
    try:
        res = client._graphql_request("""
        mutation updateFlow($id: ID!, $input: FlowInput!) {
          updateFlow(id: $id, input: $input) {
            flow { id name }
            errors { key message }
          }
        }
        """, {"id": "40764", "input": {"name": "PRD_Awareness_Flow"}})
        print(json.dumps(res, indent=2, ensure_ascii=False)[:400])
    except Exception as e:
        print(f"updateFlow error: {e}")
