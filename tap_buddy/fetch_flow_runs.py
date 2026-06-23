import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    
    print("=== Fetching Recent FlowRuns ===")
    query = """
    query {
      flowRuns(opts: { limit: 10, order: DESC }) {
        id
        flowId
        contactId
        status
        insertedAt
        updatedAt
      }
    }
    """
    try:
        res = client._graphql_request(query, {})
        flow_runs = res.get("data", {}).get("flowRuns", [])
        for fr in flow_runs:
            print(json.dumps(fr, indent=2))
    except Exception as e:
        print(f"Error fetching flowRuns: {e}")

if __name__ == "__main__":
    run()
