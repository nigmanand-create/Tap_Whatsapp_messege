import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    
    print("=== Checking recent messages for Group 12125 ===")
    query = """
    query {
      messages(filter: { groupId: 12125 }, opts: { limit: 10 }) {
        id
        body
        flowId
        insertedAt
      }
    }
    """
    try:
        res = client._graphql_request(query, {})
        messages = res.get("data", {}).get("messages", [])
        if messages:
            print(f"Found {len(messages)} recent messages.")
            for msg in messages:
                print(f"[{msg['insertedAt']}] (Flow: {msg['flowId']}): {msg['body']}")
        else:
            print("No messages found.")
            
        print("\n=== Raw Response ===")
        print(json.dumps(res.get("data", {}), indent=2))
        if res.get("errors"):
            print("Errors:", json.dumps(res["errors"], indent=2))
            
    except Exception as e:
        print(f"Error checking messages: {e}")

if __name__ == "__main__":
    run()
