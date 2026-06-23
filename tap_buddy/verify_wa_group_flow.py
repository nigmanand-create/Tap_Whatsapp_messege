import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    
    print("=== Testing startWaGroupFlow ===")
    mutation1 = """
    mutation startWaGroupFlow($waGroupId: ID!, $flowId: ID!) {
      startWaGroupFlow(waGroupId: $waGroupId, flowId: $flowId) {
        success
        errors { key message }
      }
    }
    """
    variables1 = {
        "waGroupId": "12125",
        "flowId": "40067"
    }
    try:
        res1 = client._graphql_request(mutation1, variables1)
        print("startWaGroupFlow Response:", json.dumps(res1.get("data", {}), indent=2))
        if res1.get("errors"):
            print("GraphQL Errors:", json.dumps(res1["errors"], indent=2))
    except Exception as e:
        print(f"Error testing startWaGroupFlow: {e}")

    print("\n=== Testing startWaGroupCollectionFlow ===")
    mutation2 = """
    mutation startWaGroupCollectionFlow($groupId: ID!, $flowId: ID!) {
      startWaGroupCollectionFlow(groupId: $groupId, flowId: $flowId) {
        success
        errors { key message }
      }
    }
    """
    variables2 = {
        "groupId": "20996",
        "flowId": "40067"
    }
    try:
        res2 = client._graphql_request(mutation2, variables2)
        print("startWaGroupCollectionFlow Response:", json.dumps(res2.get("data", {}), indent=2))
        if res2.get("errors"):
            print("GraphQL Errors:", json.dumps(res2["errors"], indent=2))
    except Exception as e:
        print(f"Error testing startWaGroupCollectionFlow: {e}")

if __name__ == "__main__":
    run()
