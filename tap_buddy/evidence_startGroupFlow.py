import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    
    print("========================================")
    print("EVIDENCE 1: Group vs Collection Behavior")
    print("========================================")
    query_group = """
    query {
      group(id: 20996) {
        group {
          id
          label
          contactsCount
          waGroupsCount
          contacts { id name }
          waGroups { id label }
        }
      }
    }
    """
    try:
        res = client._graphql_request(query_group, {})
        print(json.dumps(res.get("data", {}), indent=2))
    except Exception as e:
        print(f"Error fetching group: {e}")

    print("\n========================================")
    print("EVIDENCE 2: Flow Definition")
    print("========================================")
    query_flow = """
    query {
      exportFlow(id: 40067) {
        exportData
      }
    }
    """
    try:
        res = client._graphql_request(query_flow, {})
        export_data_str = res.get("data", {}).get("exportFlow", {}).get("exportData", "{}")
        export_data = json.loads(export_data_str)
        # Just print the first node to prove it's a contact flow
        if export_data.get("nodes"):
            print("First Node:", json.dumps(export_data["nodes"][0], indent=2))
        else:
            print("Export Data:", json.dumps(export_data, indent=2))
    except Exception as e:
        print(f"Error fetching flow: {e}")

    print("\n========================================")
    print("EVIDENCE 3: FlowRun Creation")
    print("========================================")
    query_flow_runs = """
    query {
      flowRuns(filter: { flowId: 40067 }) {
        id
        contact { id name }
        status
        insertedAt
        updatedAt
      }
    }
    """
    try:
        res = client._graphql_request(query_flow_runs, {})
        runs = res.get("data", {}).get("flowRuns", [])
        print(f"Found {len(runs)} flow runs for Flow 40067.")
        if runs:
            print(json.dumps(runs[:5], indent=2))
    except Exception as e:
        print(f"Error fetching flow runs: {e}")

    print("\n========================================")
    print("EVIDENCE 4: Node Execution Logs")
    print("========================================")
    # Check if there's any query for flow results or node logs
    query_messages = """
    query {
      messages(filter: { flowId: 40067 }, opts: { limit: 5 }) {
        id
        body
        flowId
        insertedAt
      }
    }
    """
    try:
        res = client._graphql_request(query_messages, {})
        messages = res.get("data", {}).get("messages", [])
        print(f"Found {len(messages)} messages for Flow 40067.")
        if messages:
            print(json.dumps(messages, indent=2))
    except Exception as e:
        print(f"Error fetching messages: {e}")

    print("\n========================================")
    print("EVIDENCE 5: Test startGroupFlow")
    print("========================================")
    mutation = """
    mutation startGroupFlow($groupId: ID!, $flowId: ID!) {
      startGroupFlow(groupId: $groupId, flowId: $flowId) {
        success
        errors { key message }
      }
    }
    """
    variables = {
        "groupId": "20996",
        "flowId": "40067"
    }
    try:
        res = client._graphql_request(mutation, variables)
        print("Response:", json.dumps(res.get("data", {}), indent=2))
    except Exception as e:
        print(f"Error testing startGroupFlow: {e}")

if __name__ == "__main__":
    run()
