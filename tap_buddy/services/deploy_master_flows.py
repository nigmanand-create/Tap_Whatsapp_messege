import frappe

frappe.init("tapbuddy.local", sites_path="/home/gcp-data/tap-bench/sites")
frappe.connect()

def main():
    import json
    import uuid
    import copy
    import os
    import requests
    from tap_buddy.services.glific_client import GlificClient

    TEMPLATES = {
        "builtin_priority": """🚨 *TAP Buddy Priority Alert* 🚨

*@results.call_webhook.context.alert_title*

Hello @contact.name,
@results.call_webhook.context.alert_message_body

📌 *Alert Details:*
• Priority Level: @results.call_webhook.context.priority_level
• Target Zone: @results.call_webhook.context.target_zone
• Target District: @results.call_webhook.context.target_district
• Action Deadline: @results.call_webhook.context.action_deadline

👤 *Coordinator Info:*
• Coordinator: @results.call_webhook.context.coordinator_name
• Helpline: @results.call_webhook.context.support_helpline

📄 *Resources:*
• Emergency SOP: @results.call_webhook.context.emergency_sop_document
• Reference Image: @results.call_webhook.context.reference_image""",

        "builtin_onboarding": """👋 *Welcome to TAP Buddy Onboarding & Setup!* 🎉

Hello @contact.name,
Here is the registration summary for *@results.call_webhook.context.school_name*!

🏫 *School & Program Status:*
• Program Tier: @results.call_webhook.context.program_tier
• Academic Year: @results.call_webhook.context.academic_year
• School Registrations: @results.call_webhook.context.school_registrations
• Total Registrations: @results.call_webhook.context.total_registrations
• Registration Deadline: @results.call_webhook.context.registration_deadline

🔗 *Setup Resources & Links:*
• Registration Portal: @results.call_webhook.context.registration_portal_link
• Excel Template URL: @results.call_webhook.context.excel_template_url
• Setup Guide PDF: @results.call_webhook.context.setup_guide_pdf

Please download the Excel sheet and complete your upload before the deadline!""",

        "builtin_program_announcements": """📢 *TAP Buddy Program Announcement - Week @results.call_webhook.context.week_number* 🌟

Hello @contact.name! We have an exciting upcoming session:

🌟 *Activity:* @results.call_webhook.context.activity_name
🗣️ *Speaker:* @results.call_webhook.context.speaker_name
📅 *Date & Time:* @results.call_webhook.context.event_date at @results.call_webhook.context.event_time IST

💻 *Meeting Access (@results.call_webhook.context.meeting_platform):*
• Meeting Link: @results.call_webhook.context.meeting_link
• Meeting ID: @results.call_webhook.context.meeting_id
• Passcode: @results.call_webhook.context.passcode

📚 *Learning Resources:*
• YouTube Links: @results.call_webhook.context.grade_wise_youtube_links
• Weekly Syllabus PDF: @results.call_webhook.context.weekly_syllabus_pdf
• Promotional Banner: @results.call_webhook.context.promotional_banner_img""",

        "builtin_engagement": """📊 *TAP Buddy Engagement & Nudge Report* 📈

Hello @contact.name!
Here is the latest engagement summary for *@results.call_webhook.context.zone* (Reporting Period: *@results.call_webhook.context.reporting_period*, Week @results.call_webhook.context.week_number):

📈 *Key Engagement Metrics:*
• Total Registrations: @results.call_webhook.context.registration_count
• Access Rate: @results.call_webhook.context.access_rate
• Submission Rate: @results.call_webhook.context.submission_rate
• Dropout Count: @results.call_webhook.context.dropout_count

🔗 *Quick Action Links:*
• Portal Login: @results.call_webhook.context.portal_login_url
• Mentor Booking: @results.call_webhook.context.mentor_booking_link
• Portal Help Doc: @results.call_webhook.context.portal_help_doc_pdf""",

        "builtin_feedback": """📝 *TAP Buddy Feedback & Reporting - @results.call_webhook.context.review_month* 📊

Hello @contact.name! Your insights are vital to improving our program.
Please participate in our *@results.call_webhook.context.survey_type* (Week @results.call_webhook.context.week_number):

❓ *Poll Question:* @results.call_webhook.context.poll_question_text
1️⃣ @results.call_webhook.context.poll_option_1
2️⃣ @results.call_webhook.context.poll_option_2
3️⃣ @results.call_webhook.context.poll_option_3

🔗 *Complete the Survey Form:* @results.call_webhook.context.survey_form_url

📊 *Performance Metrics:*
• Access Rate: @results.call_webhook.context.access_rate | Submission Rate: @results.call_webhook.context.submission_rate
• School Metrics: @results.call_webhook.context.school_metrics
• Program Metrics: @results.call_webhook.context.program_metrics
• Monthly Report PDF: @results.call_webhook.context.monthly_report_template_pdf
• Progress Badge: @results.call_webhook.context.progress_badge_image""",

        "builtin_celebratory": """🎉 *TAP Buddy Celebratory Spotlight - @results.call_webhook.context.award_month* 🏆

Hello @contact.name!
🏆 *Milestone Achieved:* @results.call_webhook.context.milestone_title
🌟 *Award Tier:* @results.call_webhook.context.award_tier

💌 *@results.call_webhook.context.congratulatory_message*

🏅 *Leaderboard & Achievements:*
• #1 Top School: @results.call_webhook.context.top_school
• Your Leaderboard Rank: @results.call_webhook.context.leaderboard
• Registration Count: @results.call_webhook.context.registration_count
• Submission Count: @results.call_webhook.context.submission_count
• Achievement Metrics: @results.call_webhook.context.achievement_metrics

🔗 *Rewards & Links:*
• View Leaderboard: @results.call_webhook.context.leaderboard_portal_link
• Certificate Template: @results.call_webhook.context.certificate_template_pdf
• Trophy Graphic: @results.call_webhook.context.trophy_graphic_img"""
    }

    def build_flow_structure(base_flow, flow_id, category, flow_name, fields):
        new_flow = copy.deepcopy(base_flow)
        full_name = f"TAP Buddy Master - {flow_name}"
        flow_uuid = str(uuid.uuid4())
        keyword = f"tap_{flow_id}"

        node_webhook_uuid = str(uuid.uuid4())
        node_success_uuid = str(uuid.uuid4())
        node_failure_uuid = str(uuid.uuid4())
        
        action_webhook_uuid = str(uuid.uuid4())
        action_success_uuid = str(uuid.uuid4())
        action_failure_uuid = str(uuid.uuid4())
        
        exit_success_uuid = str(uuid.uuid4())
        exit_failure_uuid = str(uuid.uuid4())
        exit_end1_uuid = str(uuid.uuid4())
        exit_end2_uuid = str(uuid.uuid4())
        
        cat_success_uuid = str(uuid.uuid4())
        cat_failure_uuid = str(uuid.uuid4())
        case_success_uuid = str(uuid.uuid4())

        msg_text = TEMPLATES.get(flow_id)
        if not msg_text:
            msg_text = f"Hello @contact.name,\n\nHere is your {flow_name} update:\n\n" + "\n".join([f"• {fld['name']}: @results.call_webhook.context.{fld['name']}" for fld in fields])

        node_webhook = {
            "uuid": node_webhook_uuid,
            "router": {
                "type": "switch",
                "operand": "@results.call_webhook.version",
                "default_category_uuid": cat_failure_uuid,
                "categories": [
                    {
                        "uuid": cat_success_uuid,
                        "name": "Success",
                        "exit_uuid": exit_success_uuid
                    },
                    {
                        "uuid": cat_failure_uuid,
                        "name": "Failure",
                        "exit_uuid": exit_failure_uuid
                    }
                ],
                "cases": [
                    {
                        "uuid": case_success_uuid,
                        "type": "has_only_text",
                        "category_uuid": cat_success_uuid,
                        "arguments": ["v1"]
                    }
                ]
            },
            "exits": [
                {
                    "uuid": exit_success_uuid,
                    "destination_uuid": node_success_uuid
                },
                {
                    "uuid": exit_failure_uuid,
                    "destination_uuid": node_failure_uuid
                }
            ],
            "actions": [
                {
                    "uuid": action_webhook_uuid,
                    "url": "http://35.223.204.121:8000/api/method/tap_buddy.dynamic_context.api.handle",
                    "type": "call_webhook",
                    "result_name": "call_webhook",
                    "method": "POST",
                    "headers": {
                        "Content-Type": "application/json",
                        "Accept": "application/json",
                        "X-Tap-Secret": "1234567890asdfgh"
                    },
                    "body": json.dumps({
                        "flow_id": flow_id,
                        "flow_category": category,
                        "contact_phone": "@contact.phone",
                        "contact_id": "@contact.id",
                        "secret": "1234567890asdfgh"
                    })
                }
            ]
        }

        node_success = {
            "uuid": node_success_uuid,
            "exits": [
                {
                    "uuid": exit_end1_uuid,
                    "destination_uuid": None
                }
            ],
            "actions": [
                {
                    "uuid": action_success_uuid,
                    "type": "send_msg",
                    "text": msg_text,
                    "quick_replies": [],
                    "labels": [],
                    "attachments": []
                }
            ]
        }

        node_failure = {
            "uuid": node_failure_uuid,
            "exits": [
                {
                    "uuid": exit_end2_uuid,
                    "destination_uuid": None
                }
            ],
            "actions": [
                {
                    "uuid": action_failure_uuid,
                    "type": "send_msg",
                    "text": "⚠️ We encountered an issue fetching your dynamic context data. Please try again later or contact support.",
                    "quick_replies": [],
                    "labels": [],
                    "attachments": []
                }
            ]
        }

        new_flow["name"] = full_name
        new_flow["uuid"] = flow_uuid
        new_flow["keywords"] = [keyword]
        new_flow["definition"]["name"] = full_name
        new_flow["definition"]["uuid"] = flow_uuid
        new_flow["definition"]["entry"] = node_webhook_uuid
        new_flow["definition"]["nodes"] = [node_webhook, node_success, node_failure]
        new_flow["definition"]["_ui"] = {
            "stickies": {},
            "nodes": {
                node_webhook_uuid: {"type": "execute_actions", "position": {"top": 100, "left": 200}},
                node_success_uuid: {"type": "execute_actions", "position": {"top": 350, "left": 100}},
                node_failure_uuid: {"type": "execute_actions", "position": {"top": 350, "left": 400}}
            }
        }

        export_container = {
            "flows": [new_flow],
            "collections": [],
            "contact_field": [],
            "interactive_templates": []
        }

        return export_container, full_name, flow_uuid, keyword, node_webhook_uuid

    c = GlificClient()
    c.ensure_valid_token()
    headers = dict(c.headers)

    print("Fetching base flow structure from 40067...")
    exp = c._graphql_request('query { exportFlow(id: "40067") { exportData } }')
    base_data = json.loads(exp["exportFlow"]["exportData"])
    base_flow = base_data["flows"][0]

    registry_path = "/home/gcp-data/tap-bench/apps/tap_buddy/tap_buddy/dynamic_context/flow_registry.json"
    with open(registry_path, "r") as f:
        registry = json.load(f)

    out_dir = "/home/gcp-data/tap-bench/apps/tap_buddy/tap_buddy/services/generated_flows"
    os.makedirs(out_dir, exist_ok=True)

    query_find = """query GetFlow($name: String!) {
      flows(filter: { name: $name }) {
        id
        uuid
        name
        keywords
        lastPublishedAt
      }
    }"""

    delete_mutation = """mutation DeleteFlow($id: ID!) {
      deleteFlow(id: $id) {
        errors { key message }
      }
    }"""

    results = []

    for flow_def in registry["flows"]:
        flow_id = flow_def["flow_id"]
        category = flow_def["category"]
        flow_name = flow_def["flow_name"]
        fields = flow_def.get("fields", [])

        print(f"\n=======================================================")
        print(f"Processing Flow: {flow_id} ({flow_name})")
        print(f"=======================================================")

        export_container, full_name, flow_uuid, keyword, node_webhook_uuid = build_flow_structure(
            base_flow, flow_id, category, flow_name, fields
        )

        # Check and delete existing flow with same name
        res_exist = c._graphql_request(query_find, {"name": full_name})
        for old_flow in res_exist.get("flows", []):
            print(f"Deleting existing flow '{full_name}' (ID: {old_flow['id']})...")
            c._graphql_request(delete_mutation, {"id": old_flow["id"]})

        out_file = os.path.join(out_dir, f"{flow_id}.json")
        with open(out_file, "w") as f:
            json.dump(export_container, f, indent=2)
        print(f"Saved exported JSON to: {out_file}")

        print(f"Importing flow '{full_name}' via GraphQL importFlow...")
        import_query = """mutation ImportFlow($flow: Json!) {
          importFlow(flow: $flow) {
            status {
              flowName
              status
            }
          }
        }"""
        res_imp = requests.post(
            c.graphql_url,
            headers=headers,
            json={"query": import_query, "variables": {"flow": json.dumps(export_container)}},
            timeout=30
        )
        if res_imp.status_code != 200 or "errors" in res_imp.json():
            print(f"ERROR during importFlow for {flow_id}:")
            print("Status Code:", res_imp.status_code)
            print("Response:", res_imp.text)
            return

        print("Import successful:", res_imp.json())

        print(f"Querying Glific to retrieve Numeric ID and verify UUID for '{full_name}'...")
        res_find = c._graphql_request(query_find, {"name": full_name})
        matching_flows = res_find.get("flows", [])
        if not matching_flows:
            print(f"ERROR: Could not find imported flow by name '{full_name}'!")
            return
        
        # Sort by ID descending to get the newest one
        flow_obj = sorted(matching_flows, key=lambda x: int(x["id"]), reverse=True)[0]
        glific_id = flow_obj["id"]
        glific_uuid = flow_obj["uuid"]
        print(f"Found Flow in Glific -> ID: {glific_id}, UUID: {glific_uuid}")

        print(f"Publishing Flow ID {glific_id} (UUID: {glific_uuid})...")
        publish_query = """mutation PublishFlow($uuid: UUID4!) {
          publishFlow(uuid: $uuid) {
            success
            errors {
              key
              message
            }
          }
        }"""
        res_pub = requests.post(
            c.graphql_url,
            headers=headers,
            json={"query": publish_query, "variables": {"uuid": glific_uuid}},
            timeout=30
        )
        pub_json = res_pub.json()
        print("Publish response:", pub_json)
        if res_pub.status_code != 200 or "errors" in pub_json.get("data", {}).get("publishFlow", {}):
            print(f"WARNING/ERROR during publishFlow for {flow_id}:")
            print("Response:", res_pub.text)

        res_find2 = c._graphql_request(query_find, {"name": full_name})
        flow_obj2 = sorted(res_find2.get("flows", []), key=lambda x: int(x["id"]), reverse=True)[0]
        pub_time = flow_obj2.get("lastPublishedAt")
        status_str = "Published" if pub_time else "Draft (Not Published)"
        print(f"Final Status: {status_str} (lastPublishedAt: {pub_time})")

        results.append({
            "flow_id": flow_id,
            "category": category,
            "numeric_id": glific_id,
            "uuid": glific_uuid,
            "name": full_name,
            "keywords": [keyword],
            "published_status": status_str,
            "last_published_at": str(pub_time),
            "json_filename": f"{flow_id}.json",
            "webhook_node_uuid": node_webhook_uuid,
            "glific_url": f"https://staging.glific.com/flows/{glific_id}"
        })

    print("\n=======================================================")
    print("ALL 6 MASTER FLOWS SUCCESSFULLY DEPLOYED!")
    print("=======================================================")
    print(json.dumps(results, indent=2))

    report_path = "/home/gcp-data/tap-bench/apps/tap_buddy/tap_buddy/services/deployment_results.json"
    with open(report_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Saved deployment results to {report_path}")

if __name__ == "__main__":
    main()
