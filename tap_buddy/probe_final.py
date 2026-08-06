"""
Probe correct shape for publishFlow, importFlow and how to edit flow nodes.
Usage: bench --site tapbuddy.local execute tap_buddy.probe_final.run
"""
import frappe
import json


def run():
    from tap_buddy.services.redis_utils import get_redis_conn
    conn = get_redis_conn()
    conn.delete("tap_buddy:cb:glific")
    print("Circuit breaker reset.")

    from tap_buddy.services.glific_client import GlificClient
    client = GlificClient()

    # 1: introspect publishFlow return type
    print("\n=== 1: introspect PublishFlowResult fields ===")
    try:
        res = client._graphql_request("""
        {
          __type(name: "PublishFlowResult") {
            fields { name type { name kind ofType { name } } }
          }
        }
        """)
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # 2: introspect ImportFlowResult fields
    print("\n=== 2: introspect ImportFlowResult fields ===")
    try:
        res = client._graphql_request("""
        {
          __type(name: "ImportFlowResult") {
            fields { name type { name kind ofType { name } } }
          }
        }
        """)
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error: {e}")

    # 3: introspect ImportFlowStatus fields
    print("\n=== 3: introspect ImportFlowStatus fields ===")
    try:
        res = client._graphql_request("""
        {
          __type(name: "ImportFlowStatus") {
            fields { name type { name kind ofType { name } } }
          }
        }
        """)
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"Error: {e}")
