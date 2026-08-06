"""
Evidence Extractor — Pass 2 (PostgreSQL compatible)
"""
import json
import subprocess
import frappe


def extract_evidence_pass2():
    if not getattr(frappe.local, "site", None):
        frappe.init(site="tapbuddy.local")
        frappe.connect()

    campaigns = [
        ("TAP-2026-00340", "40586", "builtin_onboarding",            "00d7ik53nf"),
        ("TAP-2026-00341", "40588", "builtin_engagement",            "01u6qnt06f"),
        ("TAP-2026-00342", "40587", "builtin_program_announcements", "03b5qh7h0i"),
        ("TAP-2026-00343", "40590", "builtin_celebratory",           "04umia041p"),
    ]

    # ============================================================
    # A: Full Audit Log columns (PostgreSQL information_schema)
    # ============================================================
    print("\n" + "=" * 80)
    print("  A — AUDIT LOG: ALL COLUMNS + FULL ROW DATA")
    print("=" * 80)

    cols_result = frappe.db.sql(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'tabDynamic Context Audit Log'
        ORDER BY ordinal_position
        """,
        as_list=True,
    )
    all_col_names = [r[0] for r in cols_result]
    print(f"\nAll columns: {all_col_names}\n")

    col_list = ", ".join(f'"{c}"' for c in all_col_names)
    for c_name, flow_id, flow_key, audit_id in campaigns:
        rows = frappe.db.sql(
            f'SELECT {col_list} FROM "tabDynamic Context Audit Log" WHERE name = %s',
            (audit_id,),
            as_dict=True,
        )
        if rows:
            r = rows[0]
            print(f"\n{'─'*60}")
            print(f"Campaign: {c_name} | Audit Log: {audit_id}")
            for col in all_col_names:
                val = r.get(col)
                if val not in (None, "", 0):
                    print(f"  {col:40s}: {str(val)[:300]}")
        else:
            print(f"\nCampaign: {c_name} | Audit Log: {audit_id} — NOT FOUND")

    # ============================================================
    # B: Discover tables matching message/delivery/glific/whatsapp
    # ============================================================
    print("\n" + "=" * 80)
    print("  B — DB TABLE DISCOVERY")
    print("=" * 80)

    for pattern in ('%message%', '%deliver%', '%glific%', '%whatsapp%', '%log%'):
        tables = frappe.db.sql(
            "SELECT table_name FROM information_schema.tables WHERE table_name ILIKE %s AND table_schema = 'public' ORDER BY table_name",
            (pattern,),
            as_list=True,
        )
        names = [t[0] for t in tables]
        if names:
            print(f"\nPattern '{pattern}': {names}")

    # ============================================================
    # C: Dispatch Attempt — all columns for the 4 campaigns
    # ============================================================
    print("\n" + "=" * 80)
    print("  C — DISPATCH ATTEMPT: ALL COLUMNS")
    print("=" * 80)

    da_cols = frappe.db.sql(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'tabDispatch Attempt'
        ORDER BY ordinal_position
        """,
        as_list=True,
    )
    da_col_names = [r[0] for r in da_cols]
    print(f"Dispatch Attempt columns: {da_col_names}")

    da_col_list = ", ".join(f'"{c}"' for c in da_col_names)
    for c_name, flow_id, flow_key, audit_id in campaigns:
        rows = frappe.db.sql(
            f'SELECT {da_col_list} FROM "tabDispatch Attempt" WHERE campaign = %s ORDER BY attempt_time DESC LIMIT 1',
            (c_name,),
            as_dict=True,
        )
        if rows:
            r = rows[0]
            print(f"\n{'─'*60}")
            print(f"Campaign: {c_name} | Dispatch Attempt: {r.get('name')}")
            for col in da_col_names:
                val = r.get(col)
                if val not in (None, "", 0):
                    print(f"  {col:40s}: {str(val)[:500]}")

    # ============================================================
    # D: Frappe error/info logs around 02:19-02:20 UTC
    # ============================================================
    print("\n" + "=" * 80)
    print("  D — SERVER LOG LINES AROUND THE DISPATCH WINDOW")
    print("=" * 80)

    LOG_FILES = [
        "/home/gcp-data/tap-bench/logs/web.error.log",
        "/home/gcp-data/tap-bench/logs/worker.error.log",
        "/home/gcp-data/tap-bench/logs/web.log",
        "/home/gcp-data/tap-bench/logs/worker.log",
        "/home/gcp-data/tap-bench/sites/tapbuddy.local/logs/frappe.log",
        "/home/gcp-data/tap-bench/sites/tapbuddy.local/logs/error.log",
        "/home/gcp-data/tap-bench/sites/tapbuddy.local/logs/dynamic_context.log",
    ]

    PATTERNS = [
        "02:19:4", "02:19:5", "02:20:0",
        "dynamic_context", "bq_webhook", "call_webhook",
        "BigQuery", "builtin_onboarding", "builtin_engagement",
        "builtin_program", "builtin_celebratory",
        "get_onboarding", "get_engagement", "get_announcements", "get_celebratory",
        "TAP-2026-00340", "TAP-2026-00341", "TAP-2026-00342", "TAP-2026-00343",
        "00d7ik53nf", "01u6qnt06f", "03b5qh7h0i", "04umia041p",
    ]
    grep_pattern = "|".join(PATTERNS)

    for lf in LOG_FILES:
        try:
            result = subprocess.run(
                ["grep", "-E", grep_pattern, lf],
                capture_output=True, text=True, timeout=10,
            )
            output = result.stdout.strip()
            if output:
                print(f"\n--- {lf} ---")
                for line in output.splitlines()[:60]:
                    print(f"  {line}")
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"  Error reading {lf}: {e}")

    # ============================================================
    # E: Correct Glific GraphQL — introspect then query wAMessages
    # ============================================================
    print("\n" + "=" * 80)
    print("  E — GLIFIC API: INTROSPECT + GROUP MESSAGES")
    print("=" * 80)

    try:
        from tap_buddy.services.glific_client import GlificClient
        client = GlificClient()

        # Step 1: List all available query fields
        introspect_q = """
        query {
            __schema {
                queryType {
                    fields { name }
                }
            }
        }
        """
        resp = client._graphql_request(introspect_q)
        fields = resp.get("data", {}).get("__schema", {}).get("queryType", {}).get("fields", [])
        field_names = sorted([f["name"] for f in fields])
        print(f"\nGlific query fields: {field_names}")

        wa_message_fields = [f for f in field_names if "message" in f.lower() or "wa" in f.lower() or "group" in f.lower() or "flow" in f.lower()]
        print(f"Relevant fields: {wa_message_fields}")

        # Step 2: Query wAMessages for group 12125
        CAMPAIGN_FLOW_MAP = [
            ("TAP-2026-00340", "40586", "builtin_onboarding"),
            ("TAP-2026-00341", "40588", "builtin_engagement"),
            ("TAP-2026-00342", "40587", "builtin_program_announcements"),
            ("TAP-2026-00343", "40590", "builtin_celebratory"),
        ]

        # Try fetching wA group messages
        q_wa_messages = """
        query {
            wAMessages(filter: { waGroup: { id: 12125 } }, opts: { limit: 10, order: DESC }) {
                id
                body
                type
                insertedAt
                waGroup { id label }
            }
        }
        """
        try:
            resp = client._graphql_request(q_wa_messages)
            msgs = resp.get("data", {}).get("wAMessages") or []
            errors = resp.get("errors")
            print(f"\nwAMessages for WAGroup 12125:")
            if msgs:
                for m in msgs:
                    print(f"  ID: {m.get('id')} | Type: {m.get('type')} | At: {m.get('insertedAt')}")
                    print(f"  Body: {m.get('body')}")
                    print()
            else:
                print(f"  None returned. Errors: {errors}")
        except Exception as e:
            print(f"  wAMessages error: {e}")

        # Try getFlowRuns via flowGet
        for c_name, flow_id, flow_key in CAMPAIGN_FLOW_MAP:
            print(f"\n--- Campaign: {c_name} | Flow: {flow_id} ---")
            q_flow_get = """
            query GetFlow($id: ID) {
                flow(filter: { id: $id }) {
                    id
                    name
                    uuid
                    status
                    updatedAt
                }
            }
            """
            try:
                resp = client._graphql_request(q_flow_get, variables={"id": flow_id})
                data = resp.get("data", {}).get("flow")
                errs = resp.get("errors")
                if data:
                    print(f"  Flow Name  : {data.get('name')}")
                    print(f"  UUID       : {data.get('uuid')}")
                    print(f"  Status     : {data.get('status')}")
                    print(f"  Updated At : {data.get('updatedAt')}")
                else:
                    print(f"  No data. Errors: {errs}")
            except Exception as e:
                print(f"  flow query error: {e}")

    except Exception as e:
        print(f"  Glific connection error: {e}")

    print("\n" + "=" * 80)
    print("  PASS 2 COMPLETE")
    print("=" * 80)
