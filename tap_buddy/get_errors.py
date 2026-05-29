import frappe

def execute():
    errors = frappe.get_all("Error Log", filters={"method": ["like", "%webhook%"]}, fields=["method", "error"], limit=10, order_by="creation desc")
    for e in errors:
        print(f"Method: {e.method}")
        print(e.error)
        print("-" * 50)
