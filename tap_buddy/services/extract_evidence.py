"""
Production Evidence Extractor — Dynamic Context V3 UAT
Pulls raw, unmodified production records for 4 UAT campaigns across all evidence layers.
"""
import json
import frappe
from frappe.utils import get_datetime


def extract_evidence():
    if not getattr(frappe.local, "site", None):
        frappe.init(site="tapbuddy.local")
        frappe.connect()

    campaigns = [
        ("TAP-2026-00340", "40586", "builtin_onboarding"),
        ("TAP-2026-00341", "40588", "builtin_engagement"),
        ("TAP-2026-00342", "40587", "builtin_program_announcements"),
        ("TAP-2026-00343", "40590", "builtin_celebratory"),
    ]

    # ============================================================
    # LAYER 1: Pull raw "Dispatch Attempt" records (most recent)
    # ============================================================
    print("\n" + "=" * 80)
    print("  LAYER 1 — DISPATCH ATTEMPTS (latest per campaign)")
    print("=" * 80)
    dispatch_map = {}
    for c_name, flow_id, flow_key in campaigns:
        attempts = frappe.db.sql(
            """
            SELECT name, campaign, recipient, school, phone_number, message,
                   status, attempt_time, retry_count, idempotency_key,
                   provider_message_id, api_response, error_message, terminal_failure,
                   whatsapp_group
            FROM `tabDispatch Attempt`
            WHERE campaign = %s
            ORDER BY attempt_time DESC
            LIMIT 1
            """,
            (c_name,),
            as_dict=True,
        )
        if attempts:
            a = attempts[0]
            dispatch_map[c_name] = a
            print(f"\nCampaign: {c_name}")
            print(f"  Dispatch Attempt ID     : {a['name']}")
            print(f"  Status                  : {a['status']}")
            print(f"  Attempt Time (UTC)      : {a['attempt_time']}")
            print(f"  Recipient               : {a['recipient']}")
            print(f"  WhatsApp Group          : {a['whatsapp_group']}")
            print(f"  Phone Number            : {a['phone_number']}")
            print(f"  Provider Message ID     : {a['provider_message_id']}")
            print(f"  Idempotency Key         : {a['idempotency_key']}")
            print(f"  Error Message           : {a['error_message']}")
            print(f"  Terminal Failure        : {a['terminal_failure']}")
            print(f"  Retry Count             : {a['retry_count']}")
            print(f"  Message/Payload Sent    : {a['message']}")
            print(f"  API Response (raw)      :")
            print(f"    {a['api_response']}")
        else:
            print(f"\nCampaign: {c_name} — NO dispatch attempt found.")

    # ============================================================
    # LAYER 2: Dynamic Context Audit Logs (latest per campaign flow)
    # ============================================================
    print("\n" + "=" * 80)
    print("  LAYER 2 — DYNAMIC CONTEXT AUDIT LOGS (latest per flow)")
    print("=" * 80)
    audit_map = {}
    for c_name, flow_id, flow_key in campaigns:
        logs = frappe.db.sql(
            """
            SELECT name, request_id, flow_id, category, status, cache_status,
                   execution_time_ms, routine_executed, error_message, creation
            FROM `tabDynamic Context Audit Log`
            WHERE flow_id = %s
            ORDER BY creation DESC
            LIMIT 1
            """,
            (flow_key,),
            as_dict=True,
        )
        if logs:
            al = logs[0]
            audit_map[c_name] = al
            print(f"\nCampaign: {c_name} (Flow Key: {flow_key})")
            print(f"  Audit Log ID            : {al['name']}")
            print(f"  Request ID              : {al['request_id']}")
            print(f"  Flow ID (key)           : {al['flow_id']}")
            print(f"  Category                : {al['category']}")
            print(f"  Status                  : {al['status']}")
            print(f"  Cache Status            : {al['cache_status']}")
            print(f"  Execution Time          : {al['execution_time_ms']}ms")
            print(f"  Routine Executed (BQ)   : {al['routine_executed']}")
            print(f"  Error Message           : {al['error_message']}")
            print(f"  Created At (UTC)        : {al['creation']}")
        else:
            print(f"\nCampaign: {c_name} (Flow Key: {flow_key}) — NO audit log found.")

    # ============================================================
    # LAYER 3: Webhook Request Logs
    # ============================================================
    print("\n" + "=" * 80)
    print("  LAYER 3 — WEBHOOK REQUEST LOGS (last 20, all)")
    print("=" * 80)
    webhook_logs = frappe.db.sql(
        """
        SELECT name, webhook, reference_doctype, reference_document,
               url, user, data, response, error, creation
        FROM `tabWebhook Request Log`
        ORDER BY creation DESC
        LIMIT 20
        """,
        as_dict=True,
    )
    if webhook_logs:
        for wl in webhook_logs:
            print(f"\nWebhook Log ID          : {wl['name']}")
            print(f"  Created At (UTC)      : {wl['creation']}")
            print(f"  Webhook               : {wl['webhook']}")
            print(f"  Reference DocType     : {wl['reference_doctype']}")
            print(f"  Reference Document    : {wl['reference_document']}")
            print(f"  URL                   : {wl['url']}")
            print(f"  User                  : {wl['user']}")
            print(f"  Error                 : {wl['error']}")
            print(f"  Request Data          :")
            print(f"    {wl['data']}")
            print(f"  Response              :")
            print(f"    {wl['response']}")
    else:
        print("  No Webhook Request Logs found.")

    # ============================================================
    # LAYER 4: Message Log records (final delivered messages)
    # ============================================================
    print("\n" + "=" * 80)
    print("  LAYER 4 — MESSAGE LOGS (raw delivered message records)")
    print("=" * 80)
    for c_name, flow_id, flow_key in campaigns:
        msg_logs = frappe.db.sql(
            """
            SELECT name, campaign, school, phone_number, message,
                   api_response, provider_message_id, status,
                   sent_at, delivered_at, read_at, whatsapp_group
            FROM `tabMessage Log`
            WHERE campaign = %s
            ORDER BY sent_at DESC
            LIMIT 3
            """,
            (c_name,),
            as_dict=True,
        )
        if msg_logs:
            print(f"\nCampaign: {c_name}")
            for ml in msg_logs:
                print(f"  Message Log ID          : {ml['name']}")
                print(f"  Status                  : {ml['status']}")
                print(f"  Sent At (UTC)           : {ml['sent_at']}")
                print(f"  Delivered At (UTC)      : {ml['delivered_at']}")
                print(f"  Read At (UTC)           : {ml['read_at']}")
                print(f"  Phone Number            : {ml['phone_number']}")
                print(f"  WhatsApp Group          : {ml['whatsapp_group']}")
                print(f"  Provider Message ID     : {ml['provider_message_id']}")
                print(f"  API Response (raw)      : {ml['api_response']}")
                print(f"  MESSAGE TEXT (exact)    :")
                print(f"    >>>{ml['message']}<<<")
        else:
            print(f"\nCampaign: {c_name} — No Message Log records found.")

    # ============================================================
    # LAYER 5: Re-execute the BQ TVF in-process and show exact webhook response
    # ============================================================
    print("\n" + "=" * 80)
    print("  LAYER 5 — LIVE BQ TVF RESULTS (re-executed now, exact webhook payload)")
    print("=" * 80)

    TVF_ROUTINES = {
        "TAP-2026-00340": ("get_onboarding_context_v1",   "builtin_onboarding"),
        "TAP-2026-00341": ("get_engagement_context_v1",   "builtin_engagement"),
        "TAP-2026-00342": ("get_announcements_context_v1","builtin_program_announcements"),
        "TAP-2026-00343": ("get_celebratory_context_v1",  "builtin_celebratory"),
    }

    # Get a real phone from the WAG recipient
    sample_phone = frappe.db.get_value(
        "Dispatch Attempt",
        {"campaign": "TAP-2026-00340"},
        "phone_number",
        order_by="attempt_time desc",
    ) or "919876543210"

    from tap_buddy.services.bigquery_executor import execute_tvf, JSONEncoderCustom
    for c_name, (routine, flow_key) in TVF_ROUTINES.items():
        print(f"\nCampaign: {c_name}")
        print(f"  TVF Routine             : {routine}")
        print(f"  Phone Used              : {sample_phone}")
        try:
            rows = execute_tvf(routine, {"phone": sample_phone})
            if rows:
                payload = json.loads(json.dumps(rows[0], cls=JSONEncoderCustom))
                print(f"  Webhook Response JSON   :")
                print(json.dumps(payload, indent=4, ensure_ascii=False))

                # --- Placeholder audit ---
                print(f"\n  Placeholder Audit:")
                placeholder_found = False
                for k, v in payload.items():
                    val_str = str(v)
                    if "@contact." in val_str or "@results." in val_str:
                        print(f"    ❌ UNRESOLVED: {k} = {v}")
                        placeholder_found = True
                    else:
                        print(f"    ✅ RESOLVED  : {k} = {v}")
                if not placeholder_found:
                    print(f"\n  ✅ ZERO unresolved placeholders in TVF payload for {c_name}.")
            else:
                print(f"  ⚠️  TVF returned empty rows.")
        except Exception as e:
            print(f"  ❌ ERROR executing TVF: {e}")

    # ============================================================
    # LAYER 6: Glific delivery confirmation via API
    # ============================================================
    print("\n" + "=" * 80)
    print("  LAYER 6 — GLIFIC GROUP FLOW DELIVERY STATUS (via GraphQL)")
    print("=" * 80)
    try:
        from tap_buddy.services.glific_client import GlificClient
        client = GlificClient()
        FLOW_IDS = [40586, 40588, 40587, 40590]
        CAMPAIGN_IDS = ["TAP-2026-00340", "TAP-2026-00341", "TAP-2026-00342", "TAP-2026-00343"]

        for camp_id, flow_id in zip(CAMPAIGN_IDS, FLOW_IDS):
            # Query runs for this flow ID in the last 2 hours
            query = """
            query FlowRuns($flowId: ID!) {
                flowRuns(filter: { flow: { id: $flowId } }, opts: { limit: 5, order: DESC }) {
                    id
                    startedAt
                    endedAt
                    status
                    contact {
                        id
                        name
                        phone
                    }
                }
            }
            """
            try:
                resp = client._graphql_request(query, variables={"flowId": str(flow_id)})
                runs = resp.get("data", {}).get("flowRuns", [])
                print(f"\nCampaign: {camp_id} (Glific Flow ID: {flow_id})")
                if runs:
                    for r in runs:
                        print(f"  Flow Run ID             : {r.get('id')}")
                        print(f"  Status                  : {r.get('status')}")
                        print(f"  Started At              : {r.get('startedAt')}")
                        print(f"  Ended At                : {r.get('endedAt')}")
                        contact = r.get("contact") or {}
                        print(f"  Contact ID              : {contact.get('id')}")
                        print(f"  Contact Name            : {contact.get('name')}")
                        print(f"  Contact Phone           : {contact.get('phone')}")
                else:
                    errors = resp.get("errors")
                    print(f"  ⚠️  No flow runs returned. Errors: {errors}")
            except Exception as e:
                print(f"  ❌ Glific API error for flow {flow_id}: {e}")
    except Exception as e:
        print(f"  ❌ Could not connect to Glific: {e}")

    print("\n" + "=" * 80)
    print("  EVIDENCE EXTRACTION COMPLETE")
    print("=" * 80)
