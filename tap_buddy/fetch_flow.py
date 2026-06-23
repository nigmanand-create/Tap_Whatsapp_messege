import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    print("=== Fetching Flow 40067 ===")
    query = """
    query {
      flow(id: "40067") {
        id
        name
        status
      }
    }
    """
    try:
        res = client._graphql_request(query, {})
        flow = res.get("data", {}).get("flow", {})
        print(json.dumps(flow, indent=2))
    except Exception as e:
        print(f"Error fetching flow: {e}")

if __name__ == "__main__":
    run()
