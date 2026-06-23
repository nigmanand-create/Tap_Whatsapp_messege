import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    
    print("=== Fetching messages ===")
    
    query = """
    query {
      messages(filter: { term: "Warm" }, opts: { limit: 10 }) {
        id
        body
        insertedAt
        waGroup {
          id
        }
      }
    }
    """
    try:
        res = client._graphql_request(query, {})
        messages = res.get("data", {}).get("messages", [])
        print(f"\n--- Found {len(messages)} messages ---")
        for m in messages:
            print(f"ID: {m.get('id')}, Body: {m.get('body')}, Group: {m.get('waGroup', {}).get('id')}")
            
    except Exception as e:
        print(f"Error fetching messages: {e}")

if __name__ == "__main__":
    run()
