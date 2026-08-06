"""
Introspect what Json type importFlow expects - find the correct input shape.
Usage: bench --site tapbuddy.local execute tap_buddy.probe_import_input.run
"""
import frappe
import json


def run():
    from tap_buddy.services.redis_utils import get_redis_conn
    conn = get_redis_conn()
    conn.delete("tap_buddy:cb:glific")

    from tap_buddy.services.glific_client import GlificClient
    client = GlificClient()

    # Introspect the importFlow mutation argument type
    print("=== Introspect importFlow mutation ===")
    try:
        res = client._graphql_request("""
        {
          __schema {
            mutationType {
              fields {
                name
                args { name type { name kind ofType { name kind ofType { name } } } }
              }
            }
          }
        }
        """)
        mutations = res.get("__schema", {}).get("mutationType", {}).get("fields", [])
        for m in mutations:
            if "import" in m["name"].lower() or "flow" in m["name"].lower():
                print(f"Mutation: {m['name']}")
                for arg in m.get("args", []):
                    tname = arg.get("type", {})
                    print(f"  Arg: {arg['name']} -> {json.dumps(tname)}")
    except Exception as e:
        print(f"Introspect error: {e}")

    # Try minimal importFlow with different keys
    print("\n=== Try importFlow with 'definition' key ===")
    try:
        res = client._graphql_request("""
        mutation importFlow($flow: Json!) {
          importFlow(flow: $flow) {
            status { flowName status }
          }
        }
        """, {"flow": {"definition": {}}})
        print(json.dumps(res, indent=2)[:400])
    except Exception as e:
        print(f"Error: {e}")

    # Try with flow_name key
    print("\n=== Try importFlow with direct flow object ===")
    try:
        res = client._graphql_request("""
        mutation importFlow($flow: Json!) {
          importFlow(flow: $flow) {
            status { flowName status }
          }
        }
        """, {"flow": {"name": "test", "uuid": "29597896-17d1-407a-8d11-a05b16dd4250"}})
        print(json.dumps(res, indent=2)[:400])
    except Exception as e:
        print(f"Error: {e}")

    # Try with single flow object (not wrapped in flows array)
    print("\n=== Try importFlow with single flow ===")
    try:
        res = client._graphql_request("""
        mutation importFlow($flow: Json!) {
          importFlow(flow: $flow) {
            status { flowName status }
          }
        }
        """, {"flow": {"uuid": "29597896-17d1-407a-8d11-a05b16dd4250", "type": "messaging", "name": "PRD_Awareness_Flow", "nodes": [], "spec_version": "14.3.0", "language": "base", "expire_after_minutes": 10080}})
        print(json.dumps(res, indent=2)[:600])
    except Exception as e:
        print(f"Error: {e}")
