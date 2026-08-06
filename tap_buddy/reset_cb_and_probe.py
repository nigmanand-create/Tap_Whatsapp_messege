"""
Reset Glific circuit breaker and then probe importFlow + publishFlow correct shapes.
Usage: bench --site tapbuddy.local execute tap_buddy.reset_cb_and_probe.run
"""
import frappe
import json


def run():
    from tap_buddy.services.redis_utils import record_api_success, get_redis_conn
    
    # Reset circuit breaker
    PREFIX = "tap_buddy:"
    conn = get_redis_conn()
    key = f"{PREFIX}cb:glific"
    conn.delete(key)
    print(f"Circuit breaker key '{key}' deleted. Circuit is now CLOSED.")

    from tap_buddy.services.glific_client import GlificClient
    client = GlificClient()

    # Test 1: importFlow with correct status subfields
    print("\n=== importFlow status { flowName status } ===")
    try:
        res = client._graphql_request("""
        mutation importFlow($flow: Json!) {
          importFlow(flow: $flow) {
            status { flowName status }
          }
        }
        """, {"flow": {}})
        print(json.dumps(res, indent=2)[:600])
    except Exception as e:
        print(f"Error: {e}")

    # Test 2: publishFlow return shape
    print("\n=== publishFlow return shape ===")
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
        print(f"Error: {e}")

    # Test 3: What return shape does publishFlow accept?
    print("\n=== publishFlow no return fields ===")
    try:
        res = client._graphql_request("""
        mutation publishFlow($uuid: UUID4!) {
          publishFlow(uuid: $uuid) {
            published
          }
        }
        """, {"uuid": "29597896-17d1-407a-8d11-a05b16dd4250"})
        print(json.dumps(res, indent=2)[:600])
    except Exception as e:
        print(f"Error: {e}")
