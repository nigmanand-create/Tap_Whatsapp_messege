import frappe
from frappe.utils import now_datetime
import time
from tap_buddy.tasks.scheduler import dispatch_campaign


def run():
    frappe.db.rollback()

    print("\n=== REGRESSION TEST 1: Contact Flow ===")
    schools = frappe.get_all("School", filters={"whatsapp_number": ["is", "set"]}, fields=["name", "whatsapp_number"], limit=1)
    school_name = schools[0].name if schools else None

    if not school_name:
        print("SKIP: No school with phone for contact test")
    else:
        camp = frappe.new_doc("TAP Campaign")
        camp.campaign_name = f"Regression-Contact-{int(time.time())}"
        camp.campaign_type = "Flow"
        camp.campaign_channel = "Direct"
        camp.send_date = now_datetime().date()
        camp.targeting_type = "Single School"
        camp.school_name = school_name
        camp.glific_flow = "40067"
        camp.insert(ignore_permissions=True)
        camp.submit()
        frappe.db.commit()
        dispatch_campaign(camp.name)
        frappe.db.commit()
        recs = frappe.get_all("Campaign Recipient", filters={"campaign": camp.name}, fields=["name", "status", "failure_reason"])
        for r in recs:
            print(f"CONTACT | {camp.name} | Recipient={r.name} | Status={r.status} | Error={r.failure_reason}")
            att = frappe.get_all("Dispatch Attempt", filters={"recipient": r.name}, fields=["name", "status", "provider_message_id", "error_message"], limit=1)
            for a in att:
                print(f"  Attempt={a.name} | Status={a.status} | ProviderID={a.provider_message_id} | Error={a.error_message}")

    print("\n=== REGRESSION TEST 2: WA Group Flow ===")
    camp2 = frappe.new_doc("TAP Campaign")
    camp2.campaign_name = f"Regression-WAGroup-{int(time.time())}"
    camp2.campaign_type = "Flow"
    camp2.campaign_channel = "Group"
    camp2.send_date = now_datetime().date()
    camp2.targeting_type = "WhatsApp Group"
    camp2.target_group = "WAG-12125"
    camp2.glific_flow = "40067"
    camp2.insert(ignore_permissions=True)
    camp2.submit()
    frappe.db.commit()
    dispatch_campaign(camp2.name)
    frappe.db.commit()
    recs2 = frappe.get_all("Campaign Recipient", filters={"campaign": camp2.name}, fields=["name", "status", "failure_reason"])
    for r in recs2:
        print(f"WA_GROUP | {camp2.name} | Recipient={r.name} | Status={r.status} | Error={r.failure_reason}")
        att = frappe.get_all("Dispatch Attempt", filters={"recipient": r.name}, fields=["name", "status", "provider_message_id", "error_message"], limit=1)
        for a in att:
            print(f"  Attempt={a.name} | Status={a.status} | ProviderID={a.provider_message_id} | Error={a.error_message}")

    print("\n=== REGRESSION TEST 3: Direct Group Messaging (Template) ===")
    # Template campaign to a WA group (sendMessageInWaGroup path)
    camp3 = frappe.new_doc("TAP Campaign")
    camp3.campaign_name = f"Regression-DirectMsg-{int(time.time())}"
    camp3.campaign_type = "Template"
    camp3.campaign_channel = "Group"
    camp3.send_date = now_datetime().date()
    camp3.targeting_type = "WhatsApp Group"
    camp3.target_group = "WAG-12125"
    camp3.template = "Test_Template_1782206623"  # existing approved template
    camp3.insert(ignore_permissions=True)
    camp3.submit()
    frappe.db.commit()
    dispatch_campaign(camp3.name)
    frappe.db.commit()
    recs3 = frappe.get_all("Campaign Recipient", filters={"campaign": camp3.name}, fields=["name", "status", "failure_reason"])
    for r in recs3:
        print(f"DIRECT_MSG | {camp3.name} | Recipient={r.name} | Status={r.status} | Error={r.failure_reason}")
        att = frappe.get_all("Dispatch Attempt", filters={"recipient": r.name}, fields=["name", "status", "provider_message_id", "error_message"], limit=1)
        for a in att:
            print(f"  Attempt={a.name} | Status={a.status} | ProviderID={a.provider_message_id} | Error={a.error_message}")

    print("\n=== DONE ===")
