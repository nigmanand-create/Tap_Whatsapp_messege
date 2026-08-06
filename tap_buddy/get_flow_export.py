"""
Get full export of flow 40764 to inspect existing nodes.
Usage: bench --site tapbuddy.local execute tap_buddy.get_flow_export.run
"""
import frappe
import json


def run():
    from tap_buddy.services.glific_client import GlificClient
    client = GlificClient()

    FLOW_ID = "40764"
    FLOW_UUID = "29597896-17d1-407a-8d11-a05b16dd4250"

    # Get full export
    print("\n=== Full Export of Flow 40764 ===")
    res = client._graphql_request("""
    query exportFlow($id: ID!) {
      exportFlow(id: $id) {
        exportData
        errors { key message }
      }
    }
    """, {"id": FLOW_ID})

    raw = res.get("exportFlow", {}).get("exportData", "{}")
    flow_data = json.loads(raw)

    # Pretty print the nodes
    flows = flow_data.get("flows", [])
    if flows:
        definition = flows[0].get("definition", flows[0])
        nodes = definition.get("nodes", [])
        print(f"Number of nodes: {len(nodes)}")
        for i, node in enumerate(nodes):
            print(f"\n--- Node {i+1}: {node.get('uuid', '?')[:16]}... ---")
            for action in node.get("actions", []):
                print(f"  type: {action.get('type')}")
                text = action.get("text", "")
                if text:
                    print(f"  text: {text[:120]}")
                msg = action.get("msg", {})
                if msg:
                    print(f"  msg: {json.dumps(msg)[:120]}")
            for exit_ in node.get("exits", []):
                print(f"  exit -> {exit_.get('destination_uuid', 'END')}")

    # Also save the full export to a file for reference
    with open("/tmp/flow_40764_export.json", "w") as f:
        json.dump(flow_data, f, indent=2, ensure_ascii=False)
    print("\nFull export saved to /tmp/flow_40764_export.json")

    # Print the spec_version and other metadata
    if flows:
        defn = flows[0].get("definition", flows[0])
        print(f"\nSpec version: {defn.get('spec_version')}")
        print(f"Flow UUID: {defn.get('uuid')}")
        print(f"Flow type: {defn.get('type')}")
        print(f"Language: {defn.get('language')}")
        print(f"Vars: {defn.get('vars', [])}")
