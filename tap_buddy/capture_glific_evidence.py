import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    
    print("=== Fetching Recent Messages ===")
    # Fetch latest 10 messages
    query = """
    query {
      messages(opts: { limit: 10, order: DESC }) {
        id
        body
        insertedAt
        groupId
        flow
        type
        bspStatus
        errors
      }
    }
    """
    try:
        res = client._graphql_request(query, {})
        messages = res.get("data", {}).get("messages", [])
        for m in messages:
            print(json.dumps(m, indent=2))
    except Exception as e:
        print(f"Error fetching messages: {e}")

if __name__ == "__main__":
    run()
