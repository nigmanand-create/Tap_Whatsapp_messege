import frappe
def run():
    try:
        frappe.get_doc({
            "doctype": "LMS Student",
            "lms_id": "test_stu_99",
            "student_name": "John Doe",
            "phone": "+918595701049",
            "grade": "10th",
            "language": "en"
        }).insert()
        print("Student Created!")
    except Exception as e:
        print("Failed:", type(e).__name__)
        print(getattr(e, 'message', str(e)))
