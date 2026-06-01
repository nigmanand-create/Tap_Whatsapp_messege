import frappe

def run():
    print("🧹 Force Deleting All TAP Buddy Data...")
    
    # 1. Cancel and Delete all Campaigns
    campaigns = frappe.get_all("TAP Campaign", pluck="name")
    for c in campaigns:
        try:
            doc = frappe.get_doc("TAP Campaign", c)
            if doc.docstatus == 1:
                doc.cancel()
            frappe.delete_doc("TAP Campaign", c, force=1, ignore_permissions=True)
            print(f"Deleted Campaign: {c}")
        except Exception as e:
            print(f"Failed to delete Campaign {c}: {e}")

    # 2. Delete all Students
    students = frappe.get_all("LMS Student", pluck="name")
    for s in students:
        try:
            frappe.delete_doc("LMS Student", s, force=1, ignore_permissions=True)
            print(f"Deleted Student: {s}")
        except Exception as e:
            print(f"Failed to delete Student {s}: {e}")

    # 3. Delete all Schools
    schools = frappe.get_all("School", pluck="name")
    for s in schools:
        try:
            frappe.delete_doc("School", s, force=1, ignore_permissions=True)
            print(f"Deleted School: {s}")
        except Exception as e:
            print(f"Failed to delete School {s}: {e}")
            
    # 4. Delete WhatsApp Templates
    templates = frappe.get_all("WhatsApp Template", pluck="name")
    for t in templates:
        try:
            frappe.delete_doc("WhatsApp Template", t, force=1, ignore_permissions=True)
            print(f"Deleted Template: {t}")
        except Exception as e:
            pass

    frappe.db.commit()
    print("✅ Full Force Cleanup Complete!")
