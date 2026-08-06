import json
import requests
import frappe

def fetch_flows_raw():
    settings = frappe.get_single("TAP Buddy Settings")
    token = settings.get_password("glific_access_token")
    url = f"{settings.glific_url.rstrip('/')}/api/v1/graphql"
    
    headers = {
        "Authorization": token,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    
    flow_ids = [40761, 40764, 40762, 40763, 40765, 40766]
    flows_data = {}
    
    query = """
    query flow($id: ID!) {
      flow(id: $id) {
        flow {
          id
          name
          status
          definition
        }
      }
    }
    """
    
    for fid in flow_ids:
        try:
            print(f"Fetching flow {fid}...")
            resp = requests.post(url, headers=headers, json={"query": query, "variables": {"id": str(fid)}})
            resp.raise_for_status()
            j = resp.json()
            flow_info = j.get("data", {}).get("flow", {}).get("flow", {})
            if "definition" in flow_info and flow_info["definition"]:
                flow_info["definition"] = json.loads(flow_info["definition"])
            flows_data[str(fid)] = flow_info
        except Exception as e:
            print(f"Error fetching flow {fid}: {e}")
            if 'resp' in locals():
                print(resp.text)
            flows_data[str(fid)] = {"error": str(e)}
            
    out_path = "/Users/blackstar/.gemini/antigravity-ide/brain/c6019ddc-914d-4fb3-a01f-10c248bc520c/scratch/glific_flows_data.json"
    with open(out_path, "w") as f:
        json.dump(flows_data, f, indent=2)
    print(f"Successfully saved flow definitions to {out_path}")
