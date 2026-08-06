"""
QA Smoke Test Campaign Creator + Post-execution Reporter
=========================================================
Creates 6 one-time campaigns targeting WA Group 12125,
scheduled 5 minutes apart starting from current server time + 5 min.
Stops immediately and reports the exact error if any creation fails.
After all campaigns have executed, generates a full PASS/FAIL report.
"""
import json
import time
import frappe
from frappe.utils import now_datetime, add_to_date, get_datetime


# ─── Campaign definitions ──────────────────────────────────────────────────────
WA_GROUP_FRAPPE_ID = "WAG-12125"  # Frappe DocName — group_name="Testing Group", glific_id=12125

CAMPAIGN_IDS = [
    ("QA Smoke Test - Priority",      "TAP-2026-00329", "40585"),
    ("QA Smoke Test - Onboarding",    "TAP-2026-00330", "40586"),
    ("QA Smoke Test - Announcements", "TAP-2026-00331", "40587"),
    ("QA Smoke Test - Engagement",    "TAP-2026-00332", "40588"),
    ("QA Smoke Test - Feedback",      "TAP-2026-00333", "40589"),
    ("QA Smoke Test - Celebratory",   "TAP-2026-00334", "40590"),
]


def check_campaign_status():
    """Quick live status check — run at any time to see current state."""
    import frappe
    print(f"\n{'Campaign':<42} {'Status':<16} {'Recv':<6} {'Sent':<6} {'Fail':<6} {'Total'}")
    print(f"  {'-'*40:<42} {'-'*14:<16} {'-'*4:<6} {'-'*4:<6} {'-'*4:<6} {'-'*4}")
    for name, frappe_id, flow_id in CAMPAIGN_IDS:
        try:
            c = frappe.get_doc("TAP Campaign", frappe_id)
            recs = frappe.get_all("Campaign Recipient", filters={"campaign": frappe_id},
                                  fields=["status"])
            sent  = sum(1 for r in recs if r.status in ("Sent", "Delivered", "Read"))
            fail  = sum(1 for r in recs if r.status == "Failed")
            flag  = "✅" if c.status in ("Completed", "Sent") else ("⏳" if c.status == "Running" else "⏰")
            print(f"  {flag} {name:<40} {c.status:<16} {len(recs):<6} {sent:<6} {fail:<6} {c.total_recipients or 0}")
        except Exception as e:
            print(f"  ❌ {name}: {e}")


CAMPAIGNS = [
    {"name": "QA Smoke Test - Priority",      "flow_id": "40585", "flow_key": "builtin_priority"},
    {"name": "QA Smoke Test - Onboarding",    "flow_id": "40586", "flow_key": "builtin_onboarding"},
    {"name": "QA Smoke Test - Announcements", "flow_id": "40587", "flow_key": "builtin_program_announcements"},
    {"name": "QA Smoke Test - Engagement",    "flow_id": "40588", "flow_key": "builtin_engagement"},
    {"name": "QA Smoke Test - Feedback",      "flow_id": "40589", "flow_key": "builtin_feedback"},
    {"name": "QA Smoke Test - Celebratory",   "flow_id": "40590", "flow_key": "builtin_celebratory"},
]

INTERVAL_MINUTES = 5


def test():
    # ── Step 0: Verify WA Group exists ────────────────────────────────────────
    print("=" * 68)
    print("  QA Smoke Test — Campaign Creator")
    print("=" * 68)
    
    try:
        wa_group = frappe.get_doc("WhatsApp Group", WA_GROUP_FRAPPE_ID)
        print(f"\n[OK] WhatsApp Group found: '{wa_group.group_name}' (ID: {WA_GROUP_FRAPPE_ID})")
        print(f"     Glific Group ID: {wa_group.glific_group_id}")
    except frappe.DoesNotExistError:
        print(f"\n[FATAL] WhatsApp Group '{WA_GROUP_FRAPPE_ID}' not found in Frappe.")
        print("  Fix: Check the Frappe DocName for WhatsApp Group 12125.")
        _list_wa_groups()
        return

    # ── Step 1: Delete any pre-existing QA campaigns (clean slate) ────────────
    print("\n[INFO] Checking for pre-existing QA campaigns...")
    for c in CAMPAIGNS:
        existing = frappe.get_all("TAP Campaign", filters={"campaign_name": c["name"]}, fields=["name"])
        for ex in existing:
            frappe.delete_doc("TAP Campaign", ex.name, ignore_permissions=True, force=True)
            print(f"  [DELETED] Pre-existing campaign: {ex.name}")
    frappe.db.commit()

    # ── Step 2: Create campaigns ───────────────────────────────────────────────
    print("\n[INFO] Creating 6 QA Smoke Test campaigns...")
    base_time = now_datetime()
    created_campaigns = []

    for idx, c in enumerate(CAMPAIGNS):
        send_dt = add_to_date(base_time, minutes=INTERVAL_MINUTES * (idx + 1))
        
        try:
            doc = frappe.new_doc("TAP Campaign")
            doc.campaign_name   = c["name"]
            doc.campaign_type   = "Flow"
            doc.glific_flow     = c["flow_id"]
            doc.targeting_type  = "WhatsApp Group"
            doc.target_group    = WA_GROUP_FRAPPE_ID
            doc.send_date       = send_dt
            doc.status          = "Scheduled"
            doc.insert(ignore_permissions=True)
            frappe.db.commit()

            created_campaigns.append({
                "frappe_id":   doc.name,
                "name":        c["name"],
                "flow_id":     c["flow_id"],
                "flow_key":    c["flow_key"],
                "send_date":   str(send_dt),
            })
            print(f"  [OK]  {c['name']}")
            print(f"        Frappe ID  : {doc.name}")
            print(f"        Flow ID    : {c['flow_id']}")
            print(f"        Scheduled  : {send_dt}")

        except Exception as e:
            print(f"\n[FATAL] Campaign creation FAILED for '{c['name']}':")
            print(f"        {type(e).__name__}: {e}")
            print("\nAborting. No further campaigns will be created.")
            frappe.db.rollback()
            return

    # ── Step 3: Verification table ────────────────────────────────────────────
    print("\n" + "=" * 68)
    print("  CAMPAIGN CREATION SUMMARY")
    print("=" * 68)
    print(f"  {'Campaign Name':<40} {'Frappe ID':<20} {'Flow ID':<10} {'Scheduled Time'}")
    print(f"  {'-'*38:<40} {'-'*18:<20} {'-'*8:<10} {'-'*22}")
    for c in created_campaigns:
        print(f"  {c['name']:<40} {c['frappe_id']:<20} {c['flow_id']:<10} {c['send_date']}")

    # ── Step 4: Verify status in DB ───────────────────────────────────────────
    print("\n[INFO] Verifying all campaigns are Scheduled...")
    all_scheduled = True
    for c in created_campaigns:
        status = frappe.db.get_value("TAP Campaign", c["frappe_id"], "status")
        flag = "✅" if status == "Scheduled" else "❌"
        print(f"  {flag} {c['name']} → status: {status}")
        if status != "Scheduled":
            all_scheduled = False

    if all_scheduled:
        print("\n✅ All 6 campaigns created and verified as Scheduled.")
    else:
        print("\n❌ One or more campaigns are NOT in Scheduled state — investigate.")

    # ── Step 5: Persist context for report generation ─────────────────────────
    context_path = "/tmp/qa_campaign_context.json"
    with open(context_path, "w") as f:
        json.dump(created_campaigns, f, indent=2, default=str)
    print(f"\n[INFO] Campaign context saved to {context_path}")
    print("[INFO] Run generate_report() after last campaign fires to get PASS/FAIL results.")
    
    last_campaign_time = created_campaigns[-1]["send_date"]
    print(f"\n[INFO] Last campaign scheduled at: {last_campaign_time}")
    print(f"[INFO] To generate report, run this after that time:")
    print(f"       bench --site tapbuddy.local execute tap_buddy.services.test_query_messages.generate_report")


def generate_report():
    """
    Run this after the last campaign has had time to execute.
    Reads context, queries DB, and prints full PASS/FAIL report.
    """
    print("=" * 68)
    print("  QA Smoke Test — Post-Execution Report")
    print("=" * 68)

    context_path = "/tmp/qa_campaign_context.json"
    try:
        with open(context_path) as f:
            campaigns = json.load(f)
    except FileNotFoundError:
        print("[ERROR] Context file not found. Run test() first.")
        return

    results = []

    for c in campaigns:
        frappe_id = c["frappe_id"]
        flow_id   = c["flow_id"]
        flow_key  = c["flow_key"]
        name      = c["name"]

        # Campaign status
        camp = frappe.get_doc("TAP Campaign", frappe_id)
        camp_status = camp.status
        sent_count  = camp.sent_count or 0
        total       = camp.total_recipients or 0
        failed      = camp.failed_count or 0

        # Recipient dispatch status
        recipients = frappe.get_all(
            "Campaign Recipient",
            filters={"campaign": frappe_id},
            fields=["name", "status", "failure_reason", "sent_time"]
        )
        rec_statuses = [r.status for r in recipients]
        rec_sent     = sum(1 for r in recipients if r.status in ("Sent", "Delivered", "Read"))
        rec_failed   = sum(1 for r in recipients if r.status == "Failed")

        # Dynamic Context Audit Log entries
        audit_entries = frappe.get_all(
            "Dynamic Context Audit Log",
            filters={"flow_id": flow_key},
            fields=["request_id", "status", "execution_time_ms", "cache_status", "error_message"],
            order_by="creation desc",
            limit=5
        )
        audit_count   = len(audit_entries)
        audit_ok      = sum(1 for a in audit_entries if a.status == "Success")
        audit_fail    = sum(1 for a in audit_entries if a.status != "Success")
        avg_ms        = (sum(a.execution_time_ms or 0 for a in audit_entries) / max(audit_count, 1))

        # Dispatch Attempts
        attempts = frappe.get_all(
            "Dispatch Attempt",
            filters={"campaign": frappe_id},
            fields=["status", "error_message", "api_response"]
        )
        attempts_ok   = sum(1 for a in attempts if a.status == "Sent")
        attempts_fail = sum(1 for a in attempts if a.status == "Failed")

        # PASS/FAIL determination
        dispatched_ok = rec_sent > 0 or attempts_ok > 0
        bq_ok         = audit_ok > 0
        no_errors     = rec_failed == 0 and attempts_fail == 0

        overall = "✅ PASS" if (dispatched_ok and bq_ok) else "❌ FAIL"
        if not dispatched_ok:
            reason = "Flow not dispatched"
        elif not bq_ok:
            reason = "No successful audit log entry (webhook/BQ failure)"
        else:
            reason = "OK"

        results.append({
            "name":           name,
            "flow_id":        flow_id,
            "campaign_status": camp_status,
            "recipients":     len(recipients),
            "rec_sent":       rec_sent,
            "rec_failed":     rec_failed,
            "audit_entries":  audit_count,
            "audit_ok":       audit_ok,
            "audit_fail":     audit_fail,
            "avg_bq_ms":      round(avg_ms, 1),
            "attempts_ok":    attempts_ok,
            "attempts_fail":  attempts_fail,
            "overall":        overall,
            "reason":         reason,
        })

    # Print report
    print(f"\n{'Flow':<42} {'Camp.Status':<14} {'Recv':<6} {'Sent':<6} {'Fail':<6} {'BQ Logs':<8} {'Avg ms':<8} {'Result'}")
    print(f"{'-'*40:<42} {'-'*12:<14} {'-'*4:<6} {'-'*4:<6} {'-'*4:<6} {'-'*6:<8} {'-'*6:<8} {'-'*10}")
    for r in results:
        print(
            f"  {r['name']:<40} {r['campaign_status']:<14} {r['recipients']:<6} "
            f"{r['rec_sent']:<6} {r['rec_failed']:<6} {r['audit_ok']}/{r['audit_entries']:<6} "
            f"{r['avg_bq_ms']:<8} {r['overall']}"
        )

    print("\n── Detailed Audit Log Entries ──────────────────────────────────────────")
    for c in campaigns:
        audit_entries = frappe.get_all(
            "Dynamic Context Audit Log",
            filters={"flow_id": c["flow_key"]},
            fields=["request_id", "status", "execution_time_ms", "cache_status", "routine_executed", "error_message"],
            order_by="creation desc",
            limit=3
        )
        print(f"\n  {c['name']} ({c['flow_key']}) — {len(audit_entries)} recent entries:")
        for a in audit_entries:
            print(f"    request_id={a.request_id} | status={a.status} | {a.execution_time_ms}ms | cache={a.cache_status}")
            if a.error_message:
                print(f"    ERROR: {a.error_message}")

    # Summary
    total_pass = sum(1 for r in results if "PASS" in r["overall"])
    total_fail = sum(1 for r in results if "FAIL" in r["overall"])
    print("\n" + "=" * 68)
    print(f"  FINAL RESULT: {total_pass}/6 PASS   {total_fail}/6 FAIL")
    print(f"  Overall: {'✅ ALL PASS — Smoke test complete!' if total_fail == 0 else '❌ FAILURES DETECTED — see table above'}")
    print("=" * 68)


def _list_wa_groups():
    """Helper: print all WhatsApp Groups in Frappe to help find the right one."""
    groups = frappe.get_all("WhatsApp Group", fields=["name", "group_name", "glific_group_id"], limit=20)
    print("\nAvailable WhatsApp Groups in Frappe:")
    for g in groups:
        print(f"  name={g.name}  group_name={g.group_name}  glific_id={g.glific_group_id}")
