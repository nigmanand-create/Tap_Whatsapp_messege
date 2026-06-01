import frappe
from tap_buddy.services.lms_school_sync import _upsert_school as upsert_school

def test_falsy_sync():
    frappe.init(site="tapbuddy.local")
    frappe.connect()
    
    # Clean DB
    frappe.db.sql("DELETE FROM `tabSchool`")
    frappe.db.sql("DELETE FROM `tabLMS Student`")
    frappe.db.commit()
    
    # 1. Test School Sync Falsy Masking
    print("=== School Sync Falsy Masking ===")
    
    school_doc = frappe.get_doc({
        "doctype": "School",
        "school_name": "Test School 1",
        "lms_id": "TS1",
        "principal_name": "John Doe",
        "lms_school_status": "Active"
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    
    print(f"Before Sync: principal_name='{school_doc.principal_name}'")
    
    raw_lms_school = {
        "name": "TS1",
        "name1": "Test School 1",
        "headmaster_name": "", # Cleared
        "headmaster_phone": "",
        "status": "Inactive"
    }
    
    upsert_school(raw_lms_school)
    school_doc.reload()
    
    print(f"After Sync:  principal_name='{school_doc.principal_name}'")
    print(f"-> Falsy Masking active for School: {school_doc.principal_name == 'John Doe'}")
    
    # 2. Test Student Sync Falsy Masking
    print("\n=== Student Sync Falsy Masking ===")
    
    student_doc = frappe.get_doc({
        "doctype": "LMS Student",
        "lms_id": "ST1",
        "student_name": "Alice",
        "section": "A",
        "grade": "10",
        "glific_id": "123",
        "phone": "999999"
    }).insert(ignore_permissions=True)
    frappe.db.commit()
    
    print(f"Before Sync: section='{student_doc.section}', grade='{student_doc.grade}', glific_id='{student_doc.glific_id}'")
    
    raw = {
        "name1": "Alice",
        "glific_id": "", # Cleared
        "grade": 0,      # Falsy grade
        "section": "",   # Cleared
        "status": "Active",
        "gender": ""
    }
    
    student_doc.update({
        "student_name":  raw.get("name1") or student_doc.get("student_name"),
        "phone":         "999999",
        "glific_id":     raw.get("glific_id") or student_doc.get("glific_id"),
        "grade":         raw.get("grade") or student_doc.get("grade"),
        "section":       raw.get("section") or student_doc.get("section"),
        "gender":        raw.get("gender") or student_doc.get("gender"),
        "lms_status":    raw.get("status") or student_doc.get("lms_status"),
        "school":        student_doc.get("school"),
        "lms_school_id": raw.get("school_id") or student_doc.get("lms_school_id"),
    })
    
    print(f"After Sync:  section='{student_doc.section}', grade='{student_doc.grade}', glific_id='{student_doc.glific_id}'")
    print(f"-> Falsy Masking active for Student section: {student_doc.section == 'A'}")
    print(f"-> Falsy Masking active for Student grade (0): {student_doc.grade == '10'}")
    print(f"-> Falsy Masking active for glific_id: {student_doc.glific_id == '123'}")

if __name__ == "__main__":
    test_falsy_sync()
