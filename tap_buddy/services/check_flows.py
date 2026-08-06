import frappe
import json
from tap_buddy.services.glific_client import GlificClient

def test_dynamic_context():
    from tap_buddy.dynamic_context.registry import FlowRegistry
    from tap_buddy.dynamic_context.builder import ContextBuilder
    from tap_buddy.dynamic_context.utils import format_versioned_response

    registry = FlowRegistry()
    for flow_key in ["builtin_onboarding", "builtin_engagement", "builtin_program_announcements", "builtin_celebratory"]:
        print(f"\n==========================================")
        print(f"  TESTING DYNAMIC CONTEXT: {flow_key}")
        print(f"==========================================")
        config = registry.get_flow_config(flow_id=flow_key)
        if not config:
            print("No config found!")
            continue
        print(f"Fields: {[f.name for f in config.fields]}")
        builder = ContextBuilder(registry=registry)
        payload = {"flow_id": flow_key, "contact": {"phone": "919876543210"}, "bypass_cache": True}
        ctx = builder.build_context(payload)
        print("Context:", ctx)
def test_bq_fetch():
    import frappe
    if not getattr(frappe.local, "site", None):
        frappe.init(site="tapbuddy.local")
        frappe.connect()
    from tap_buddy.dynamic_context.providers.config import JsonFileConfigProvider
    from tap_buddy.dynamic_context.registry import FlowRegistry
    from tap_buddy.dynamic_context.builder import ContextBuilder
    
    reg = FlowRegistry(config_provider=JsonFileConfigProvider())
    builder = ContextBuilder(registry=reg)
    for flow_id in ["builtin_onboarding", "builtin_engagement", "builtin_program_announcements", "builtin_celebratory", "builtin_feedback"]:
        print(f"\n=== TESTING WITH JSON PROVIDER (ALL FIELDS): {flow_id} ===")
        cfg = reg.get_flow_config(flow_id)
        if cfg:
            print("Config fields:", [(f.name, str(f.source)) for f in cfg.fields])
        ctx = builder.build_context({"flow_id": flow_id, "contact": {"phone": "919876543210"}, "bypass_cache": True})
        print("Result context keys:", list(ctx.keys()))
        print("Result context:", ctx)

def seed_all_variables():
    import os, json, frappe
    if not getattr(frappe.local, "site", None):
        frappe.init(site="tapbuddy.local")
        frappe.connect()
    
    app_path = frappe.get_app_path("tap_buddy")
    registry_path = os.path.join(app_path, "dynamic_context", "flow_registry.json")
    with open(registry_path, "r", encoding="utf-8") as f:
        registry_data = json.load(f)
        
    for template in registry_data.get("flows", []):
        flow_id = template.get("flow_id")
        if not flow_id:
            continue
            
        if frappe.db.exists("Dynamic Context Flow Config", flow_id):
            doc = frappe.get_doc("Dynamic Context Flow Config", flow_id)
            is_new = False
        else:
            doc = frappe.new_doc("Dynamic Context Flow Config")
            doc.flow_id = flow_id
            doc.flow_name = template.get("flow_name", flow_id)
            doc.flow_category = template.get("category", "")
            doc.is_active = 1
            if template.get("bq_routine"):
                doc.bq_routine_name = template["bq_routine"]
            doc.cache_ttl = int(template.get("cache_ttl", 300))
            doc.bypass_cache = int(template.get("bypass_cache", False))
            is_new = True
            
        existing_fields = {f.field_name: f for f in getattr(doc, "fields", [])}
        modified = False
        
        for field_item in template.get("fields", []):
            var_name = field_item.get("name")
            if not var_name:
                continue
            src_str = str(field_item.get("source", "")).lower()
            target_source = "BigQuery" if src_str in ("bigquery", "bq") else "Manual Default"
            
            if var_name not in existing_fields:
                doc.append("fields", {
                    "field_name": var_name,
                    "field_source": target_source,
                    "default_value": field_item.get("default_value", ""),
                    "is_required": int(field_item.get("required", 0)),
                })
                existing_fields[var_name] = doc.fields[-1]
                modified = True
            else:
                f_doc = existing_fields[var_name]
                if f_doc.field_source != target_source:
                    f_doc.field_source = target_source
                    modified = True
                    
        if is_new:
            doc.insert(ignore_permissions=True)
            print(f"Inserted {flow_id} with all variables")
        elif modified:
            doc.save(ignore_permissions=True)
            print(f"Updated {flow_id} with missing/corrected variables")
        else:
            print(f"No changes needed for {flow_id}")
    frappe.db.commit()

def inspect_glific_flows():
    client = GlificClient()
    flow_ids = ["40586", "40587", "40588", "40589", "40590"]
    for fid in flow_ids:
        print(f"\n==========================================")
        print(f"  INSPECTING GLIFIC FLOW: {fid}")
        print(f"==========================================")
        try:
            exp = client._graphql_request(f'query {{ exportFlow(id: "{fid}") {{ exportData }} }}')
            data_str = exp["exportFlow"]["exportData"]
            d = json.loads(data_str)
            flow_def = d["flows"][0]["definition"]
            flow_name = d["flows"][0].get("name")
            print(f"Flow Name: {flow_name}")
            for node in flow_def.get("nodes", []):
                ntype = node.get("type")
                if "webhook" in str(ntype).lower() or "webhook" in str(node).lower():
                    print(f"  [Node {node.get('uuid')}] Type: {ntype}")
                    print(f"    Actions/Config: {json.dumps(node, indent=2)}")
                elif "send" in str(ntype).lower() or "message" in str(ntype).lower() or "text" in str(node).lower():
                    # check if any text has @results or @contact
                    txt = json.dumps(node)
                    if "@results" in txt or "@contact" in txt or "template" in txt:
                        print(f"  [Message Node {node.get('uuid')}] Type: {ntype}")
                        print(f"    Content: {txt}")
        except Exception as e:
            print(f"Error inspecting {fid}: {e}")

def list_campaigns():
    import frappe
    if not getattr(frappe.local, "site", None):
        frappe.init(site="tapbuddy.local")
        frappe.connect()
    meta = frappe.get_meta("TAP Campaign")
    print("TAP Campaign fields:", [f.fieldname for f in meta.fields])
    campaigns = frappe.get_all("TAP Campaign", fields=["name", "campaign_name", "status"])
    for c in campaigns:
        print(c)

def inspect_campaign_forensics():
    import frappe, json
    if not getattr(frappe.local, "site", None):
        frappe.init(site="tapbuddy.local")
        frappe.connect()
        
    print("=== FIELD METADATA ===")
    for dt_name in ["Dispatch Attempt", "Dynamic Context Audit Log", "Webhook Request Log", "Message Log"]:
        if frappe.db.exists("DocType", dt_name):
            meta = frappe.get_meta(dt_name)
            print(f"{dt_name} fields:", [f.fieldname for f in meta.fields])
        
    campaigns = ["TAP-2026-00340", "TAP-2026-00341", "TAP-2026-00342", "TAP-2026-00343"]
    for c_name in campaigns:
        print(f"\n==========================================")
        print(f"  FORENSIC INSPECTION: {c_name}")
        print(f"==========================================")
        if not frappe.db.exists("TAP Campaign", c_name):
            print(f"Campaign {c_name} not found!")
            continue
        doc = frappe.get_doc("TAP Campaign", c_name)
        print(f"1. TAP Campaign: {doc.campaign_name} ({c_name}) | Status: {doc.status} | Flow: {doc.glific_flow} | Target Group: {getattr(doc, 'target_group', None)}")
        print("   Variable Mappings:", [f"{m.variable_name} -> {m.mapping_type}:{m.value}" for m in (getattr(doc, "variable_mappings") or [])])
        print("   Flow Custom Parameters:", [f"{p.param_key} = {p.param_value}" for p in (getattr(doc, "flow_custom_parameters") or [])])
        
        # Check Dispatch Attempts
        try:
            attempts = frappe.get_all("Dispatch Attempt", filters={"campaign": c_name}, fields="*")
            print(f"2. Dispatch Attempts found: {len(attempts)}")
            for a in attempts[:5]:
                print(f"   Attempt: {a.name} | Status: {a.get('status')} | Recipient: {a.get('recipient')} | Error: {a.get('error_message')}")
        except Exception as e:
            print("   Error checking Dispatch Attempt:", e)
            
        # Check Dynamic Context Audit Logs
        try:
            audit_logs = frappe.get_all("Dynamic Context Audit Log", order_by="creation desc", limit=5, fields="*")
            print(f"3. Recent Dynamic Context Audit Logs (Total Checked: {len(audit_logs)}):")
            for log in audit_logs[:3]:
                print(f"   Log: {log.name} | Flow: {log.get('flow_id')} | Phone: {log.get('phone')} | Duration: {log.get('execution_time_ms')}ms")
                if log.get('resolved_context'):
                    print(f"   Resolved Context: {log.get('resolved_context')[:200]}...")
        except Exception as e:
            print("   Error checking Audit Logs:", e)

def dump_stage_logs():
    import frappe, json
    if not getattr(frappe.local, "site", None):
        frappe.init(site="tapbuddy.local")
        frappe.connect()
        
    campaigns = ["TAP-2026-00340", "TAP-2026-00341", "TAP-2026-00342", "TAP-2026-00343"]
    for c_name in campaigns:
        print(f"\n=======================================================")
        print(f"  FORENSIC STAGE LOGS: {c_name}")
        print(f"=======================================================")
        if not frappe.db.exists("TAP Campaign", c_name):
            print("Not found.")
            continue
        camp = frappe.get_doc("TAP Campaign", c_name)
        print(f"[Stage 1: Campaign] Name={camp.campaign_name}, Flow={camp.glific_flow}, Status={camp.status}")
        
        attempts = frappe.get_all("Dispatch Attempt", filters={"campaign": c_name}, fields="*")
        for a in attempts:
            print(f"[Stage 2: Dispatch Attempt] ID={a.name}, Time={a.attempt_time}, Status={a.status}, Recipient={a.recipient}")
            print(f"  API Response: {a.api_response}")
            print(f"  Message/Payload: {a.message}")
            
    print(f"\n=======================================================")
    print(f"  RECENT WEBHOOK REQUEST LOGS (LAST 10)")
    print(f"=======================================================")
    w_logs = frappe.get_all("Webhook Request Log", order_by="creation desc", limit=10, fields="*")
    for wl in w_logs:
        print(f"Webhook Log {wl.name} ({wl.creation}): URL={wl.url}, Error={wl.error}")
        print(f"  Data: {wl.data}")
        print(f"  Response: {wl.response}\n")
        
    print(f"\n=======================================================")
    print(f"  RECENT DYNAMIC CONTEXT AUDIT LOGS (LAST 10)")
    print(f"=======================================================")
    a_logs = frappe.get_all("Dynamic Context Audit Log", order_by="creation desc", limit=10, fields="*")
    for al in a_logs:
        print(f"Audit Log {al.name} ({al.creation}): Flow={al.flow_id}, Status={al.status}, Routine={al.routine_executed}, Time={al.execution_time_ms}ms, Error={al.error_message}")

def rerun_uat_campaigns():
    import frappe, time
    from frappe.utils import now_datetime
    from tap_buddy.tasks.scheduler import dispatch_campaign
    
    if not getattr(frappe.local, "site", None):
        frappe.init(site="tapbuddy.local")
        frappe.connect()
        
    campaigns = ["TAP-2026-00340", "TAP-2026-00341", "TAP-2026-00342", "TAP-2026-00343"]
    print("=== RE-RUNNING AFFECTED UAT CAMPAIGNS ===")
    
    for c_name in campaigns:
        if not frappe.db.exists("TAP Campaign", c_name):
            print(f"Campaign {c_name} not found.")
            continue
            
        print(f"\n[+] Preparing to re-run {c_name}...")
        # 1. Reset TAP Campaign status
        frappe.db.set_value("TAP Campaign", c_name, "status", "Scheduled")
        frappe.db.set_value("TAP Campaign", c_name, "send_date", now_datetime())
        
        # 2. Reset Campaign Recipient status
        recipients = frappe.get_all("Campaign Recipient", filters={"campaign": c_name}, fields=["name"])
        print(f"    Found {len(recipients)} recipients for {c_name}.")
        for r in recipients:
            frappe.db.set_value("Campaign Recipient", r.name, "status", "Pending")
            frappe.db.set_value("Campaign Recipient", r.name, "scheduled_time", now_datetime())
            
        frappe.db.commit()
        
        # 3. Dispatch Campaign
        print(f"    Dispatching {c_name}...")
        try:
            dispatch_campaign(c_name)
            print(f"    [SUCCESS] Dispatched {c_name}.")
        except Exception as e:
            print(f"    [ERROR] Failed to dispatch {c_name}: {e}")
            
        # Wait 5 seconds between dispatches
        time.sleep(5)
        
    print("\n=== VERIFYING NEW DISPATCH ATTEMPTS & AUDIT LOGS ===")
    time.sleep(5) # give webhooks a few seconds to process
    
    for c_name in campaigns:
        print(f"\n--- Campaign: {c_name} ---")
        camp = frappe.get_doc("TAP Campaign", c_name)
        print(f"Status: {camp.status}")
        attempts = frappe.get_all("Dispatch Attempt", filters={"campaign": c_name}, order_by="creation desc", limit=1, fields="*")
        for a in attempts:
            print(f"Latest Attempt: {a.name} | Status: {a.status} | Time: {a.attempt_time} | Error: {a.error_message}")
            print(f"API Response: {a.api_response}")
            
    print("\n--- Latest Dynamic Context Audit Logs ---")
    a_logs = frappe.get_all("Dynamic Context Audit Log", order_by="creation desc", limit=8, fields="*")
    for al in a_logs:
        print(f"Audit Log {al.name} ({al.creation}): Flow={al.flow_id}, Status={al.status}, Routine={al.routine_executed}, Time={al.execution_time_ms}ms, Error={al.error_message}")

def test_tvf_thread():
    import frappe, concurrent.futures, traceback
    if not getattr(frappe.local, "site", None):
        frappe.init(site="tapbuddy.local")
        frappe.connect()
        
    site_name = frappe.local.site
    sites_path = getattr(frappe.local, "sites_path", "/home/gcp-data/tap-bench/sites")
    
    from tap_buddy.services.bigquery_executor import execute_tvf
    
    def _worker(s_name, s_path):
        try:
            print("Worker thread started. Initial frappe.local.site:", getattr(frappe.local, "site", "NONE"))
            frappe.init(site=s_name, sites_path=s_path)
            frappe.connect()
            print("Connected in worker thread. frappe.local.site:", frappe.local.site)
            res = execute_tvf("get_onboarding_context_v1", {"phone": "919876543210"})
            print("Worker TVF result:", res)
            return res
        except Exception as e:
            print("Worker exception:", traceback.format_exc())
            raise
        finally:
            try:
                frappe.destroy()
            except Exception as e:
                print("Error in destroy:", e)
                
    print("Submitting to thread pool...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        f = executor.submit(_worker, site_name, sites_path)
        try:
            res = f.result(timeout=10)
            print("Main thread got result:", res)
        except Exception as e:
            print("Main thread got exception:", e)
