"""
Import the production Hindi flow definition for Campaign 2 (Flow 40764: PRD_Awareness_Flow).

Strategy: Use importFlow mutation with the correct Json! type (not String!).
The flow JSON must be passed directly as a dict variable (not stringified).

Usage: bench --site tapbuddy.local execute tap_buddy.import_flow_40764.run
"""
import frappe
import json
import uuid as uuid_lib


def run():
    from tap_buddy.services.glific_client import GlificClient
    client = GlificClient()

    FLOW_ID = "40764"
    FLOW_UUID = "29597896-17d1-407a-8d11-a05b16dd4250"

    # Production Hindi messages
    MSG1_TEXT = (
        "TAP को अगर एक लाइन में कहें: यह एक *मुफ़्त, सरकार द्वारा प्रमाणित प्रोग्राम है जहाँ विद्यार्थी मज़ेदार गतिविधियों के ज़रिए असली कौशल — समस्या सुलझाना, रचनात्मकता, आत्मविश्वास — सीखते हैं*, और इसमें उन्हें सिर्फ़ *20 मिनट* लगते हैं। 🎯\n\n"
        "आपको कोई अतिरिक्त काम नहीं करना है — कॉन्टेंट की ज़िम्मेदारी हमारी है, आपको बस उसे साझा करना है और बच्चों का उत्साह बढ़ाना है। 🙌\n\n"
        "आप अपनी कक्षा में बेझिझक कह सकते हैं: \"हम TAP नाम का कुछ नया और मज़ेदार शुरू कर रहे हैं — आपको एक *जीनियस*, एक *कलाकार*, या एक *बिज़नेसमैन* बनने का मौका मिलेगा!\" 😊"
    )

    MSG2_TEXT = (
        "शुरू करने से पहले, *2 मिनट* में जानिए कि TAP में आपकी क्या भूमिका होगी। 🎬\n\n"
        "यहाँ यह छोटा सा Teacher Playbook देखें: https://drive.google.com/drive/folders/1mSMfUi0TA87w1or8-wEz0XBEZqURrNr0\n\n"
        "एक छोटी सी जानकारी: आपको कुछ भी नया नहीं पढ़ाना है। 😊\n\n"
        "आपको बस अपने विद्यार्थियों के साथ इसे *साझा करना है*, उन्हें *याद दिलाना है*, और उनका *उत्साह बढ़ाना है* — बाकी सब हम संभाल लेंगे! 🙌"
    )

    # Node UUIDs (new clean UUIDs)
    NODE1_UUID  = str(uuid_lib.uuid4())
    NODE2_UUID  = str(uuid_lib.uuid4())
    ACT1_UUID   = str(uuid_lib.uuid4())
    ACT2_UUID   = str(uuid_lib.uuid4())
    EXIT1_UUID  = str(uuid_lib.uuid4())
    EXIT2_UUID  = str(uuid_lib.uuid4())

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
                NODE1_UUID: {
                    "type": "execute_actions",
                    "position": {"top": 0, "left": 0}
                },
                NODE2_UUID: {
                    "type": "execute_actions",
                    "position": {"top": 200, "left": 0}
                }
            }
        }
    }

    flow_export_payload = {
        "interactive_templates": [],
        "flows": [
            {
                "definition": flow_definition,
                "keywords": []
            }
        ],
        "contact_field": [],
        "collections": []
    }

    print(f"\n=== Importing Flow 40764: PRD_Awareness_Flow ===")
    print(f"Node 1 UUID: {NODE1_UUID}")
    print(f"Node 2 UUID: {NODE2_UUID}")
    print(f"Message 1 (preview): {MSG1_TEXT[:80]}...")
    print(f"Message 2 (preview): {MSG2_TEXT[:80]}...")

    # importFlow expects Json! not String!  — pass as dict directly
    import_mutation = """
    mutation importFlow($flow: Json!) {
      importFlow(flow: $flow) {
        status
        errors { key message }
      }
    }
    """

    try:
        result = client._graphql_request(import_mutation, {"flow": flow_export_payload})
        import_result = result.get("importFlow", {})
        status = import_result.get("status")
        errors = import_result.get("errors", [])
        print(f"\nImport status: {status}")
        if errors:
            print(f"Import errors: {errors}")
        else:
            print("\n✅ SUCCESS — Flow 40764 imported!")
            print("   Node 1: Hindi Awareness Message (TAP introduction)")
            print("   Node 2: Hindi Teacher Playbook Message (with Drive link)")
            print("   Variables: None (pure static text + static hyperlink)")
    except Exception as e:
        print(f"\n❌ importFlow failed: {e}")

        # Fallback: try with JSON string
        print("\n--- Trying fallback: passing flow as JSON string ---")
        fallback_mutation = """
        mutation importFlow($flow: String!) {
          importFlow(flow: $flow) {
            status
            errors { key message }
          }
        }
        """
        try:
            result2 = client._graphql_request(fallback_mutation, {"flow": json.dumps(flow_export_payload)})
            print(f"Fallback result: {json.dumps(result2, indent=2, ensure_ascii=False)[:400]}")
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            print("\n--- MANUAL INSTRUCTIONS ---")
            print("The Glific importFlow API is not accepting programmatic import.")
            print("Please configure the flow manually in the Glific UI at:")
            print("  https://tap.glific.com/flow/40764/edit")
            print("\nMessage 1 to paste:")
            print(MSG1_TEXT)
            print("\nMessage 2 to paste:")
            print(MSG2_TEXT)
