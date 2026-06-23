import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    
    print("=== Introspecting WaGroup and WaGroupsCollection ===")
    
    for type_name in ["WaGroup", "WaGroupsCollection", "ContactWaGroup", "WaMessage"]:
        query = f"""
        query {{
          __type(name: "{type_name}") {{
            fields {{
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
        """
        try:
            res = client._graphql_request(query, {})
            fields = res.get("__type", {}).get("fields", [])
            print(f"\n--- {type_name} Fields ---")
            for f in fields:
                field_name = f.get("name")
                field_type = f.get("type", {})
                type_str = field_type.get("name") or field_type.get("kind")
                if field_type.get("ofType"):
                    type_str += f" of {field_type['ofType'].get('name') or field_type['ofType'].get('kind')}"
                print(f"  {field_name}: {type_str}")
        except Exception as e:
            print(f"Error fetching {type_name}: {e}")

if __name__ == "__main__":
    run()
