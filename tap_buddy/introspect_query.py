import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    
    print("=== Introspecting RootQueryType ===")
    query = """
    query {
      __type(name: "RootQueryType") {
        fields {
          name
          args {
            name
            type {
              name
              kind
              ofType {
                name
                kind
              }
            }
          }
        }
      }
    }
    """
    try:
        res = client._graphql_request(query, {})
        fields = res.get("__type", {}).get("fields", [])
        for f in fields:
            name = f.get("name")
            if "message" in name.lower() or "flow" in name.lower():
                print(f"Query: {name}")
                for arg in f.get("args", []):
                    print(f"  Arg: {arg['name']} - {arg['type']}")
    except Exception as e:
        print(f"Error fetching queries: {e}")

if __name__ == "__main__":
    run()
