# -*- coding: utf-8 -*-
"""
Live Production UAT Orchestrator & Evidence Collector for VM.
Executes the 4 requested campaigns against WhatsApp Group 12125, spaced 5 minutes apart.
"""
import json
import time
from datetime import datetime, timedelta
import frappe
from frappe.utils import now_datetime, add_to_date

TARGET_GROUP_DOCNAME = "WAG-12125"  # DocName in Frappe for Group ID 12125
TARGET_GLIFIC_GROUP_ID = "12125"

CAMPAIGNS_DEF = [
    {
        "name": "UAT-REG-001",
        "title": "UAT 1 - Registration Flow",
        "flow_key": "builtin_onboarding",
        "flow_id": "40586",
        "delay_mins": 0
    },
    {
        "name": "UAT-ENG-001",
        "title": "UAT 2 - Engagement Flow",
        "flow_key": "builtin_engagement",
        "flow_id": "40588",
        "delay_mins": 5
    },
    {
        "name": "UAT-SCHED-001",
        "title": "UAT 3 - Program Schedule Flow",
        "flow_key": "builtin_program_announcements",
        "flow_id": "40587",
        "delay_mins": 10
    },
    {
        "name": "UAT-LEAD-001",
        "title": "UAT 4 - Leaderboard Celebration Flow",
        "flow_key": "builtin_celebratory",
        "flow_id": "40590",
        "delay_mins": 15
    }
]

def verify_credentials():
    """Step 1: Verify whether the production VM has valid Glific & BQ credentials."""
    print("=" * 70)
    print("  STEP 1: CREDENTIALS & CONNECTIVITY VERIFICATION")
    print("=" * 70)
    
    # Check Glific
    print("\n[?] Verifying Glific API Authentication on VM...")
    try:
        from tap_buddy.services.glific_client import GlificClient
        client = GlificClient()
        query = 'query { flow(id: "40586") { flow { id name } } }'
        res = client._graphql_request(query)
        if "errors" in res:
            print(f"[-] ERROR: Glific API returned GraphQL errors: {res['errors']}")
            return False
        flow_data = res.get("data", {}).get("flow", {}).get("flow", {})
        print(f"[+] Glific Authentication SUCCESS! Flow 40586 verified: {flow_data.get('name', 'Unknown')}")
    except Exception as e:
        print(f"[-] ERROR: Glific Authentication Failed: {e}")
        return False

    # Check BigQuery
    print("\n[?] Verifying BigQuery TVF Settings...")
    try:
        bq_settings = frappe.get_single("TAP BigQuery Settings")
        if not getattr(bq_settings, "project_id", None) or not getattr(bq_settings, "service_account_json", None):
            print("[-] WARNING: TAP BigQuery Settings not fully configured.")
        else:
            print(f"[+] BigQuery configured for project: {bq_settings.project_id}")
            print(f"[+] Service account JSON present: Yes ({len(bq_settings.service_account_json)} bytes)")
    except Exception as e:
        print(f"[-] WARNING: Could not check BigQuery settings: {e}")

    # Check WhatsApp Group record
    print(f"\n[?] Verifying Target WhatsApp Group: {TARGET_GROUP_DOCNAME} (Glific ID: {TARGET_GLIFIC_GROUP_ID})...")
    if not frappe.db.exists("WhatsApp Group", TARGET_GROUP_DOCNAME):
        print(f"[-] ERROR: WhatsApp Group {TARGET_GROUP_DOCNAME} does not exist!")
        return False
    
    group_doc = frappe.get_doc("WhatsApp Group", TARGET_GROUP_DOCNAME)
    print(f"[+] WhatsApp Group verified: '{group_doc.group_name}' (Glific Group ID: {group_doc.glific_group_id})")
    return True

def run_uat():
    """Step 2: Clean slate and schedule the 4 real campaigns 5 minutes apart."""
    if not verify_credentials():
        print("\n[!] Aborting UAT execution due to credential/setup verification failure.")
        return

    print("\n" + "=" * 70)
    print("  STEP 2: SCHEDULING 4 REAL PRODUCTION UAT CAMPAIGNS")
    print("=" * 70)

    base_time = now_datetime()
    print(f"[INFO] Server Base Time (UTC): {base_time.strftime('%Y-%m-%d %H:%M:%S')}")

    created_campaigns = []

    for c in CAMPAIGNS_DEF:
        send_dt = add_to_date(base_time, minutes=c["delay_mins"])
        
        try:
            # Create TAP Campaign
            camp = frappe.new_doc("TAP Campaign")
            camp.campaign_name = c["title"]
            camp.campaign_type = "Flow"
            camp.glific_flow = c["flow_id"]
            camp.targeting_type = "WhatsApp Group"
            camp.target_group = TARGET_GROUP_DOCNAME
            camp.status = "Scheduled"
            camp.send_date = send_dt
            camp.insert(ignore_permissions=True)
            
            # Check if recipient was auto-created
            existing_recs = frappe.get_all("Campaign Recipient", filters={"campaign": camp.name})
            if not existing_recs:
                rec = frappe.get_doc({
                    "doctype": "Campaign Recipient",
                    "campaign": camp.name,
                    "recipient_type": "Group",
                    "whatsapp_group": TARGET_GROUP_DOCNAME,
                    "status": "Pending",
                    "scheduled_time": send_dt.strftime("%Y-%m-%d %H:%M:%S")
                })
                rec.insert(ignore_permissions=True)
            
            print(f"  [OK] Scheduled: {camp.name:<18} ({c['title']:<32}) -> {send_dt.strftime('%H:%M:%S UTC')}")
            created_campaigns.append({
                "frappe_id": camp.name,
                "title": c["title"],
                "flow_id": c["flow_id"],
                "flow_key": c["flow_key"],
                "send_date": str(send_dt)
            })
        except Exception as e:
            print(f"  [FATAL] Failed to schedule {c['title']}: {e}")
            frappe.db.rollback()
            return

    frappe.db.commit()
    
    with open("/tmp/live_uat_context.json", "w") as f:
        json.dump(created_campaigns, f, indent=2)
        
    print("\n✅ All 4 UAT Campaigns scheduled successfully!")
    print(f"[INFO] Context saved to /tmp/live_uat_context.json")
    print("[INFO] To monitor status and collect evidence, run:")
    print("       bench --site tapbuddy.local execute tap_buddy.services.live_uat.collect_evidence")

def collect_evidence():
    """Step 3: Collect full forensic evidence for each campaign."""
    print("=" * 70)
    print("  STEP 3: LIVE UAT EXECUTION EVIDENCE REPORT")
    print("=" * 70)
    
    try:
        with open("/tmp/live_uat_context.json") as f:
            campaigns = json.load(f)
    except FileNotFoundError:
        print("[-] ERROR: /tmp/live_uat_context.json not found. Run run_uat() first.")
        return

    all_pass = True
    summary_rows = []

    for c in campaigns:
        camp_name = c["frappe_id"]
        flow_id = c["flow_id"]
        flow_key = c["flow_key"]
        title = c["title"]
        
        print(f"\n── Campaign: {camp_name} ({title}) ──")
        
        if not frappe.db.exists("TAP Campaign", camp_name):
            print(f"  ❌ Campaign {camp_name} not found!")
            all_pass = False
            continue
            
        camp = frappe.get_doc("TAP Campaign", camp_name)
        print(f"  Status        : {camp.status}")
        print(f"  Scheduled Time: {camp.send_date}")
        
        # Recipients
        recipients = frappe.get_all("Campaign Recipient", filters={"campaign": camp_name}, fields=["name", "status", "sent_time", "failure_reason"])
        print(f"  Recipients    : {len(recipients)}")
        for r in recipients:
            print(f"    -> Recipient ID: {r.name} | Status: {r.status} | Sent: {r.sent_time or 'N/A'}")
            if r.failure_reason:
                print(f"       Failure Reason: {r.failure_reason}")
                
        # Dispatch Attempts
        attempts = frappe.get_all("Dispatch Attempt", filters={"campaign": camp_name}, fields=["name", "status", "attempt_time", "error_message", "api_response"])
        print(f"  Dispatch Logs : {len(attempts)} attempts")
        for a in attempts:
            print(f"    -> Attempt: {a.name} | Status: {a.status} | Time: {a.attempt_time}")
            if a.error_message:
                print(f"       Error: {a.error_message}")
            if a.api_response:
                print(f"       API Response: {a.api_response[:200]}...")

        # Message Logs
        msg_logs = frappe.get_all("Message Log", filters={"campaign": camp_name}, fields=["name", "status", "sent_at", "provider_message_id", "whatsapp_group", "phone_number"])
        print(f"  Message Logs  : {len(msg_logs)} messages delivered/sent")
        for m in msg_logs:
            print(f"    -> Msg ID: {m.name} | Status: {m.status} | Sent At: {m.sent_at} | Provider ID: {m.provider_message_id}")

        # Dynamic Context Audit Log
        audit_logs = frappe.get_all("Dynamic Context Audit Log", filters={"flow_id": flow_key}, fields=["request_id", "status", "execution_time_ms", "cache_status", "routine_executed", "error_message", "creation"], order_by="creation desc", limit=3)
        print(f"  BigQuery TVFs : {len(audit_logs)} recent audit log entries for {flow_key}")
        for aud in audit_logs:
            print(f"    -> Request: {aud.request_id} | Status: {aud.status} | BQ Time: {aud.execution_time_ms}ms | Cache: {aud.cache_status} | TVF: {aud.routine_executed}")
            if aud.error_message:
                print(f"       BQ Error: {aud.error_message}")

        # Determine pass/fail for this campaign
        rec_sent = sum(1 for r in recipients if r.status in ("Sent", "Delivered", "Read"))
        rec_failed = sum(1 for r in recipients if r.status == "Failed")
        aud_ok = sum(1 for aud in audit_logs if aud.status == "Success")
        
        passed = (rec_sent > 0 and rec_failed == 0 and aud_ok > 0)
        if not passed:
            all_pass = False
            
        summary_rows.append({
            "name": camp_name,
            "title": title[:24],
            "flow": flow_key,
            "status": camp.status,
            "rec_sent": rec_sent,
            "rec_fail": rec_failed,
            "bq_ok": aud_ok,
            "result": "✅ PASS" if passed else "❌ FAIL"
        })

    print("\n" + "=" * 70)
    print("  SUMMARY TABLE")
    print("=" * 70)
    print(f"  {'Campaign ID':<18} {'Title':<26} {'Status':<12} {'Sent':<6} {'Fail':<6} {'BQ':<6} {'Result'}")
    print(f"  {'-'*18} {'-'*26} {'-'*12} {'-'*6} {'-'*6} {'-'*6} {'-'*8}")
    for r in summary_rows:
        print(f"  {r['name']:<18} {r['title']:<26} {r['status']:<12} {r['rec_sent']:<6} {r['rec_fail']:<6} {r['bq_ok']:<6} {r['result']}")

    print("\n" + "=" * 70)
    if all_pass:
        print("  FINAL STATUS: ✅ ALL 4 CAMPAIGNS SUCCESSFULLY DELIVERED!")
    else:
        print("  FINAL STATUS: ⏳ IN PROGRESS OR FAILED (See details above)")
    print("=" * 70)
