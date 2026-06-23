import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    
    print("=== Introspecting Mutations ===")
    query = """
    query {
      __schema {
        mutationType {
          name
        }
      }
    }
    """
    res = client._graphql_request(query, {})
    mutation_type_name = res.get("__schema", {}).get("mutationType", {}).get("name", "RootMutationType")
    
    query_mutations = f"""
    query {{
      __type(name: "{mutation_type_name}") {{
        fields {{
          name
          description
          args {{
            name
            type {{
              kind
              name
              ofType {{
                kind
                name
              }}
            }}
          }}
        }}
      }}
    }}
    """
    try:
        res = client._graphql_request(query_mutations, {})
        fields = res.get("__type", {}).get("fields", [])
        
        keywords = ["wagroup", "group", "flow", "trigger", "automation", "collection", "send"]
        matches = []
        for field in fields:
            name = field["name"].lower()
            if any(k in name for k in keywords):
                matches.append(field)
                
        print(f"Found {len(matches)} mutations related to {keywords}")
        for match in matches:
            args = [a["name"] for a in match.get("args", [])]
            print(f"- {match['name']}({', '.join(args)})")
            
        print("\n=== Specific Mutation Details ===")
        for match in matches:
            if "wagroup" in match["name"].lower() or "flow" in match["name"].lower():
                print(json.dumps(match, indent=2))
                
    except Exception as e:
        print(f"Error fetching mutations: {e}")

if __name__ == "__main__":
    run()
