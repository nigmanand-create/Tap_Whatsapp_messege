"""
Script to inspect and configure Glific Flow 40764 (PRD_Awareness_Flow)
using the Glific GraphQL API.

Usage:
    bench --site tapbuddy.local execute tap_buddy.configure_flow_40764.run
"""
import frappe
import json

def run():
    from tap_buddy.services.glific_client import GlificClient

    client = GlificClient()
    flow_uuid = None

    # --- STEP 1: Find all flows and locate ID 40764 ---
    print("\n=== STEP 1: Find Flow 40764 ===")
    flows = client.get_flows(is_active=True, limit=10000)
    # also get inactive
    flows_inactive = client.get_flows(is_active=False, limit=10000)
    all_flows = flows + flows_inactive
    print(f"Total flows fetched: {len(all_flows)}")
    for f in all_flows:
        if str(f.get("id")) == "40764" or "Awareness" in f.get("name", ""):
            print(f"  *** MATCH: id={f['id']}  name={f['name']}")
            flow_uuid = f.get("uuid")  # may not be in this response

    if not flow_uuid:
        print("Flow UUID not in get_flows response - need to query by ID")

    # Try fetching by ID using the flow query
    flow_query = """
    query flow($id: ID!) {
      flow(id: $id) {
        id
        name
        uuid
        flowType
        isActive
      }
    }
    """
    try:
        res = client._graphql_request(flow_query, {"id": "40764"})
        flow_data = res.get("flow", {})
        if flow_data:
            flow_uuid = flow_data.get("uuid")
            print(f"Flow 40764: name={flow_data.get('name')}, uuid={flow_uuid}, isActive={flow_data.get('isActive')}")
    except Exception as e:
        print(f"flow(id) query error: {e}")


    # --- STEP 2: Inspect current flow nodes via exportFlow ---
    print(f"\n=== STEP 2: Inspect Flow {flow_uuid} ===")
    export_query = """
    query exportFlow($id: ID!) {
      exportFlow(id: $id) {
        exportData
        errors { key message }
      }
    }
    """
    export_result = client._graphql_request(export_query, {"id": "40764"})
    export_data = export_result.get("exportFlow", {})
    errors = export_data.get("errors", [])
    if errors:
        print(f"Export errors: {errors}")
    raw_export = export_data.get("exportData", "{}")
    try:
        flow_json = json.loads(raw_export) if isinstance(raw_export, str) else raw_export
        print(f"Flow name: {flow_json.get('name', 'N/A')}")
        flows_list = flow_json.get("flows", [flow_json])
        if flows_list:
            nodes = flows_list[0].get("nodes", [])
            print(f"Current node count: {len(nodes)}")
            for node in nodes:
                ntype = node.get("type", "")
                nid = node.get("uuid", node.get("id", "?"))
                actions = node.get("actions", [])
                for a in actions:
                    atype = a.get("type", "")
                    text = a.get("text", "")[:60] if a.get("text") else ""
                    print(f"  Node {nid[:8]}... type={ntype} action={atype} text='{text}'")
    except Exception as e:
        print(f"Could not parse flow JSON: {e}")
        print(f"Raw export (first 500 chars): {str(raw_export)[:500]}")

    print("\n=== STEP 3: Prepare Campaign 2 Flow JSON ===")
    # Build the complete flow definition for Campaign 2
    # Flow structure: Start -> Message 1 -> Message 2 -> End
    msg1_text = (
        "TAP को अगर एक लाइन में कहें: यह एक *मुफ़्त, सरकार द्वारा प्रमाणित प्रोग्राम है जहाँ विद्यार्थी मज़ेदार गतिविधियों के ज़रिए असली कौशल — समस्या सुलझाना, रचनात्मकता, आत्मविश्वास — सीखते हैं*, और इसमें उन्हें सिर्फ़ *20 मिनट* लगते हैं। 🎯\n\n"
        "आपको कोई अतिरिक्त काम नहीं करना है — कॉन्टेंट की ज़िम्मेदारी हमारी है, आपको बस उसे साझा करना है और बच्चों का उत्साह बढ़ाना है। 🙌\n\n"
        "आप अपनी कक्षा में बेझिझक कह सकते हैं: \"हम TAP नाम का कुछ नया और मज़ेदार शुरू कर रहे हैं — आपको एक *जीनियस*, एक *कलाकार*, या एक *बिज़नेसमैन* बनने का मौका मिलेगा!\" 😊"
    )

    msg2_text = (
        "शुरू करने से पहले, *2 मिनट* में जानिए कि TAP में आपकी क्या भूमिका होगी। 🎬\n\n"
        "यहाँ यह छोटा सा Teacher Playbook देखें: https://drive.google.com/drive/folders/1mSMfUi0TA87w1or8-wEz0XBEZqURrNr0\n\n"
        "एक छोटी सी जानकारी: आपको कुछ भी नया नहीं पढ़ाना है। 😊\n\n"
        "आपको बस अपने विद्यार्थियों के साथ इसे *साझा करना है*, उन्हें *याद दिलाना है*, और उनका *उत्साह बढ़ाना है* — बाकी सब हम संभाल लेंगे! 🙌"
    )

    print("Message 1 (first 80 chars):", msg1_text[:80])
    print("Message 2 (first 80 chars):", msg2_text[:80])

    # Build the RapidPro/Glific flow JSON structure
    import uuid as uuid_lib

    start_uuid = "76c80b65-0000-0000-0000-000000000001"
    msg1_uuid  = "76c80b65-0000-0000-0000-000000000002"
    msg2_uuid  = "76c80b65-0000-0000-0000-000000000003"
    exit1_uuid = "76c80b65-0000-0000-0000-000000000004"
    exit2_uuid = "76c80b65-0000-0000-0000-000000000005"

    flow_definition = {
        "name": "PRD_Awareness_Flow",
        "spec_version": "13.1.0",
        "uuid": flow_uuid,
        "type": "messaging",
        "expire_after_minutes": 10080,
        "language": "hin",
        "nodes": [
            {
                "uuid": start_uuid,
                "actions": [
                    {
                        "uuid": str(uuid_lib.uuid4()),
                        "type": "send_msg",
                        "text": msg1_text,
                        "attachments": [],
                        "quick_replies": []
                    }
                ],
                "exits": [
                    {
                        "uuid": exit1_uuid,
                        "destination_uuid": msg2_uuid
                    }
                ]
            },
            {
                "uuid": msg2_uuid,
                "actions": [
                    {
                        "uuid": str(uuid_lib.uuid4()),
                        "type": "send_msg",
                        "text": msg2_text,
                        "attachments": [],
                        "quick_replies": []
                    }
                ],
                "exits": [
                    {
                        "uuid": exit2_uuid,
                        "destination_uuid": None
                    }
                ]
            }
        ],
        "localization": {}
    }

    flow_export_json = {
        "version": "13",
        "flows": [flow_definition],
        "fields": [],
        "groups": [],
        "campaigns": [],
        "triggers": []
    }

    # --- STEP 4: Import the flow ---
    print("\n=== STEP 4: Import Flow into Glific ===")
    import_query = """
    mutation importFlow($flow: String!) {
      importFlow(flow: $flow) {
        success
        errors { key message }
      }
    }
    """
    import_vars = {"flow": json.dumps(flow_export_json)}
    import_result = client._graphql_request(import_query, import_vars)
    import_data = import_result.get("importFlow", {})
    success = import_data.get("success", False)
    errs = import_data.get("errors", [])
    print(f"Import success: {success}")
    if errs:
        print(f"Import errors: {errs}")

    if success:
        print("\n✅ Flow 40764 successfully configured!")
        print("   - Node 1: Hindi Message 1 (TAP awareness)")
        print("   - Node 2: Hindi Message 2 (Teacher Playbook link)")
        print(f"\n   Flow UUID: {flow_uuid}")
        print("   No variables used (pure static text + static hyperlink).")
    else:
        print("\n⚠️  Import returned success=False. Check errors above.")
        print("The flow may need to be configured manually in the Glific UI.")
        print(f"\n--- COPY THIS INTO GLIFIC FLOW 40764 ---")
        print(f"\nMessage 1:\n{msg1_text}")
        print(f"\nMessage 2:\n{msg2_text}")
