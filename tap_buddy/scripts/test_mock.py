import frappe
from tap_buddy.services.glific_client import GlificClient

def test():
    frappe.init(site="tapbuddy.local")
    frappe.connect()
    
    settings = frappe.get_single("TAP Buddy Settings")
    client = GlificClient()
    print("is_explicit_mock:", bool(frappe.cache().get_value("mock_glific")))
    print("self.access_token:", repr(client.access_token))
    print("settings.glific_token:", repr(settings.glific_token))
    print("is_mock:", client._is_mock)

if __name__ == "__main__":
    test()
