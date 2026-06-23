import json
from tap_buddy.services.glific_client import GlificClient

def run():
    client = GlificClient()
    
    print("=== 1. Fetching Active Flows ===")
    query_flows = """
    query {
      flows(filter: { isActive: true }, opts: { limit: 15 }) {
        id
        name
      }
    }
    """
    try:
        res = client._graphql_request(query_flows, {})
        flow_list = res.get("flows", [])
    except Exception as e:
        print(f"Error fetching flows: {e}")
        return

    # Ensure 40067 is included if it's not in the first 15
    if not any(str(f["id"]) == "40067" for f in flow_list):
        flow_list.insert(0, {"id": "40067", "name": "Flow 40067"})
        
    print(f"Found {len(flow_list)} flows to analyze.")
    
    flow_data = []
    
    for f in flow_list[:12]: # analyze around 10-12
        flow_id = f["id"]
        flow_name = f["name"]
        print(f"Exporting flow {flow_id}: {flow_name}")
        query_export = f"""
        query {{
          exportFlow(id: {flow_id}) {{
            exportData
          }}
        }}
        """
        try:
            res = client._graphql_request(query_export, {})
            export_data_str = res.get("exportFlow", {}).get("exportData", "{}")
            export_data = json.loads(export_data_str)
            
            node_types = set()
            interactive_nodes = False
            requires_context = False
            requires_state = False
            
            if export_data and "flows" in export_data:
                for flow_def in export_data["flows"]:
                    nodes = flow_def.get("definition", {}).get("nodes", [])
                    for node in nodes:
                        actions = node.get("actions", [])
                        for action in actions:
                            action_type = action.get("type", "unknown")
                            node_types.add(action_type)
                            if action_type in ["ask_question", "wait", "run_action", "webhook", "set_contact_field"]:
                                requires_state = True
                            if action_type in ["ask_question", "interactive_msg"]:
                                interactive_nodes = True
                            if action_type in ["run_action", "webhook"]:
                                requires_context = True
                                
            flow_data.append({
                "id": flow_id,
                "name": flow_name,
                "node_types": list(node_types),
                "interactive": interactive_nodes,
                "requires_state": requires_state,
                "requires_context": requires_context
            })
        except Exception as e:
            print(f"Error exporting flow {flow_id}: {e}")
            
    print("\n=== MATRIX DATA ===")
    for d in flow_data:
        print(json.dumps(d))
        
if __name__ == "__main__":
    run()
