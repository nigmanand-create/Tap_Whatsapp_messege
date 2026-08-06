import frappe
import json

def export_flows():
    flow_ids = ['40761', '40764', '40762', '40763', '40765', '40766']
    flows = frappe.get_all("Glific Flow", filters={"flow_id": ("in", flow_ids)}, fields=["flow_id", "flow_name", "definition"])
    
    out_path = "/Users/blackstar/.gemini/antigravity-ide/brain/c6019ddc-914d-4fb3-a01f-10c248bc520c/scratch/glific_flows_db.json"
    
    data = {}
    for f in flows:
        data[f.flow_id] = {
            "name": f.flow_name,
            "definition": json.loads(f.definition) if f.definition else None
        }
        
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)
    print(f"Exported {len(flows)} flows to {out_path}")
