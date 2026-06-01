import frappe
def run():
    errors = frappe.get_all("Error Log", fields=["error", "method", "creation"], order_by="creation desc", limit=100)
    for e in errors:
        if "phone_number" not in e.method:
            print(f"[{e.creation}] --- Method: {e.method} ---")
            lines = e.error.strip().split('\n')
            print(lines[-1] if lines else "")
