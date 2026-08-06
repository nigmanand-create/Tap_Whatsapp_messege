"""
Final import of Campaign 2 flow (40764) using correct schema.
Usage: bench --site tapbuddy.local execute tap_buddy.do_import_flow.run
"""
import frappe
import json
import uuid as uuid_lib


def run():
    from tap_buddy.services.redis_utils import get_redis_conn
    conn = get_redis_conn()
    conn.delete("tap_buddy:cb:glific")
    print("Circuit breaker reset.")

    from tap_buddy.services.glific_client import GlificClient
    client = GlificClient()

    FLOW_UUID = "29597896-17d1-407a-8d11-a05b16dd4250"

    # Production Hindi messages
    MSG1_TEXT = (
        "TAP को अगर एक लाइन में कहें: यह एक *मुफ़्त, सरकार द्वारा प्रमाणित प्रोग्राम है जहाँ विद्यार्थी मज़ेदार गतिविधियों के ज़रिए असली कौशल — समस्या सुलझाना, रचनात्मकता, आत्मविश्वास — सीखते हैं*, और इसमें उन्हें सिर्फ़ *20 मिनट* लगते हैं। 🎯\n\n"
        "आपको कोई अतिरिक्त काम नहीं करना है — कॉन्टेंट की ज़िम्मेदारी हमारी है, आपको बस उसे साझा करना है और बच्चों का उत्साह बढ़ाना है। 🙌\n\n"
        'आप अपनी कक्षा में बेझिझक कह सकते हैं: "हम TAP नाम का कुछ नया और मज़ेदार शुरू कर रहे हैं — आपको एक *जीनियस*, एक *कलाकार*, या एक *बिज़नेसमैन* बनने का मौका मिलेगा!" 😊'
    )

    MSG2_TEXT = (
        "शुरू करने से पहले, *2 मिनट* में जानिए कि TAP में आपकी क्या भूमिका होगी। 🎬\n\n"
        "यहाँ यह छोटा सा Teacher Playbook देखें: https://drive.google.com/drive/folders/1mSMfUi0TA87w1or8-wEz0XBEZqURrNr0\n\n"
        "एक छोटी सी जानकारी: आपको कुछ भी नया नहीं पढ़ाना है। 😊\n\n"
        "आपको बस अपने विद्यार्थियों के साथ इसे *साझा करना है*, उन्हें *याद दिलाना है*, और उनका *उत्साह बढ़ाना है* — बाकी सब हम संभाल लेंगे! 🙌"
    )

    NODE1_UUID = str(uuid_lib.uuid4())
    NODE2_UUID = str(uuid_lib.uuid4())
    ACT1_UUID  = str(uuid_lib.uuid4())
    ACT2_UUID  = str(uuid_lib.uuid4())
    EXIT1_UUID = str(uuid_lib.uuid4())
    EXIT2_UUID = str(uuid_lib.uuid4())

    flow_definition = {
        "vars": ["7899fbc5-8b09-4f28-a7d5-d9912868b233"],
        "uuid": FLOW_UUID,
        "type": "messaging",
        "spec_version": "14.3.0",
        "name": "PRD_Awareness_Flow",
        "language": "base",
        "expire_after_minutes": 10080,
        "nodes": [
            {
                "uuid": NODE1_UUID,
                "actions": [
                    {
                        "uuid": ACT1_UUID,
                        "type": "send_msg",
                        "text": MSG1_TEXT,
                        "attachments": [],
                        "quick_replies": []
                    }
                ],
                "exits": [
                    {
                        "uuid": EXIT1_UUID,
                        "destination_uuid": NODE2_UUID
                    }
                ]
            },
            {
                "uuid": NODE2_UUID,
                "actions": [
                    {
                        "uuid": ACT2_UUID,
                        "type": "send_msg",
                        "text": MSG2_TEXT,
                        "attachments": [],
                        "quick_replies": []
                    }
                ],
                "exits": [
                    {
                        "uuid": EXIT2_UUID,
                        "destination_uuid": None
                    }
                ]
            }
        ],
        "localization": {},
        "_ui": {
            "nodes": {
                NODE1_UUID: {"type": "execute_actions", "position": {"top": 0, "left": 0}},
                NODE2_UUID: {"type": "execute_actions", "position": {"top": 250, "left": 0}}
            }
        }
    }

    # Glific importFlow requires a specific envelope
    flow_payload = {
        "flows": [
            {
                "definition": flow_definition,
                "keywords": []
            }
        ]
    }

    print(f"\n=== Importing Flow 40764 ===")
    print(f"Node 1: {NODE1_UUID}")
    print(f"Node 2: {NODE2_UUID}")

    # Attempt 1: importFlow with Json!
    print("\n--- Attempt: importFlow with Json ---")
    try:
        result = client._graphql_request("""
        mutation importFlow($flow: Json!) {
          importFlow(flow: $flow) {
            status {
              flowName
              status
              assistantNodeUuids
              invalidSheetNodeUuids
            }
          }
        }
        """, {"flow": flow_payload})
        statuses = result.get("importFlow", {}).get("status", [])
        print(f"Status count: {len(statuses)}")
        for s in statuses:
            print(f"  flowName: {s.get('flowName')}, status: {s.get('status')}")
            invalid = s.get("invalidSheetNodeUuids", [])
            if invalid:
                print(f"  Invalid node UUIDs: {invalid}")

        if any(s.get("status") == "success" or "success" in str(s.get("status", "")).lower() for s in statuses):
            print("\n✅ IMPORT SUCCESS!")
            # Now publish
            print("\n--- Publishing flow ---")
            pub_result = client._graphql_request("""
            mutation publishFlow($uuid: UUID4!) {
              publishFlow(uuid: $uuid) {
                success
                errors { key message }
              }
            }
            """, {"uuid": FLOW_UUID})
            pub = pub_result.get("publishFlow", {})
            pub_success = pub.get("success", False)
            pub_errors = pub.get("errors", [])
            print(f"Publish success: {pub_success}")
            if pub_errors:
                print(f"Publish errors: {pub_errors}")
        else:
            print(f"\nImport status details: {json.dumps(statuses, indent=2, ensure_ascii=False)}")

    except Exception as e:
        print(f"importFlow error: {e}")

    # Print the exact messages as fallback manual guide
    print("\n" + "="*60)
    print("MANUAL CONFIGURATION GUIDE (if API import fails)")
    print("="*60)
    print(f"\nFlow URL: https://tap.glific.com/flow/40764/edit")
    print("\n--- Message 1 (paste exactly) ---")
    print(MSG1_TEXT)
    print("\n--- Message 2 (paste exactly) ---")
    print(MSG2_TEXT)
