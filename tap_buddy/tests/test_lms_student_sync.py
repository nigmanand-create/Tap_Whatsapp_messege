import frappe
from tap_buddy.services.lms_student_sync import _school_cache, sync_all_students

def test_school_cache_invisibility_bug(monkeypatch):
    """
    Test that newly created schools do not remain invisible
    to the student sync due to a persistent module-level cache.
    """
    # Setup mock LMSClient
    class MockLMSClient:
        def get_all_students(self):
            return [{
                "name": "stu1",
                "name1": "Student One",
                "phone": "9999999999",
                "school_id": "school-cache-test"
            }]
    
    monkeypatch.setattr("tap_buddy.services.lms_student_sync.LMSClient", MockLMSClient)
    
    # Ensure polling is enabled for the test
    frappe.db.set_value("LMS Integration Settings", None, "polling_enabled", 1)

    # Clean up DB before test
    frappe.db.delete("LMS Student", {"lms_id": "stu1"})
    frappe.db.delete("School", {"lms_id": "school-cache-test"})
    
    # Scenario A: School missing
    # Run sync
    res = sync_all_students()
    assert res["status"] == "ok"
    
    # Check that school was mapped to "" locally
    stu = frappe.get_last_doc("LMS Student", filters={"lms_id": "stu1"})
    assert stu.school == "", "School should be empty because it does not exist yet"
    
    # Check that the internal cache stored the empty string
    assert "school-cache-test" in _school_cache
    assert _school_cache["school-cache-test"] == ""

    # Scenario B: School created later
    school = frappe.get_doc({
        "doctype": "School",
        "school_name": "Test School Cache",
        "lms_id": "school-cache-test",
    })
    school.insert(ignore_permissions=True)
    
    # Next sync run discovers school correctly
    # Without the fix, the cache would still hold "" and it would map to ""
    # With the fix, `sync_all_students()` calls `_school_cache.clear()`
    res2 = sync_all_students()
    assert res2["status"] == "ok"
    
    # Verify the student now has the school properly mapped
    stu.reload()
    assert stu.school == school.name, f"School should now be mapped correctly, got: {stu.school}"
