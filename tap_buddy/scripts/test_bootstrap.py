import frappe
from tap_buddy.tap_buddy.doctype.tap_buddy_settings.tap_buddy_settings import bootstrap_glific_session

def test():
    frappe.init(site="tapbuddy.local")
    frappe.connect()
    res = bootstrap_glific_session("8595701049", "Nigma@2004")
    print(f"Result: {res}")

if __name__ == "__main__":
    test()
