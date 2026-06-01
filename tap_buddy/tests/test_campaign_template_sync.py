import frappe
from frappe.utils import now_datetime
import unittest
import re
from tap_buddy.tasks.scheduler import _get_template_text

class TestCampaignTemplateSync(unittest.TestCase):
    def setUp(self):
        frappe.init(site="tapbuddy.local")
        frappe.connect()
        frappe.db.sql("DELETE FROM `tabTAP Campaign`")
        frappe.db.sql("DELETE FROM `tabWhatsApp Template` WHERE template_name IN ('test_sync_1', 'test_sync_2')")
        frappe.db.commit()

        # Create template 1 (1 variable)
        self.tmpl1 = frappe.get_doc({
            "doctype": "WhatsApp Template",
            "template_name": "test_sync_1",
            "message": "Hello {{1}}",
            "language": "English",
            "detected_params": 1
        }).insert(ignore_permissions=True)

        # Create template 2 (2 variables)
        self.tmpl2 = frappe.get_doc({
            "doctype": "WhatsApp Template",
            "template_name": "test_sync_2",
            "message": "Hi {{1}}, meet {{2}}",
            "language": "English",
            "detected_params": 2
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    def test_scenario_a_autopopulates(self):
        # Scenario A: Select template, message_template auto-populates
        camp = frappe.get_doc({
            "doctype": "TAP Campaign",
            "campaign_name": "Test Auto",
            "targeting_type": "Single School",
            "school_name": "Test School 1",
            "template": "test_sync_1",
            "send_date": now_datetime(),
            "status": "Draft"
        }).insert(ignore_permissions=True)
        
        self.assertEqual(camp.message_template, "Hello {{1}}")

    def test_scenario_b_customization_restored(self):
        # Scenario B: Attempt customization, template selection restores canonical text
        camp = frappe.get_doc({
            "doctype": "TAP Campaign",
            "campaign_name": "Test Custom",
            "targeting_type": "Single School",
            "school_name": "Test School 1",
            "template": "test_sync_1",
            "send_date": now_datetime(),
            "status": "Draft"
        }).insert(ignore_permissions=True)
        
        # Simulate user hacking the payload via API to customize the text
        camp.message_template = "Hello from Custom Text!"
        camp.save(ignore_permissions=True)
        
        # Because we enforce it during _sync_message_template on save, it should have been overwritten!
        camp.reload()
        self.assertEqual(camp.message_template, "Hello {{1}}")

        # Now change the template
        camp.template = "test_sync_2"
        camp.save(ignore_permissions=True)
        camp.reload()
        
        # It must be overwritten with tmpl2's message
        self.assertEqual(camp.message_template, "Hi {{1}}, meet {{2}}")

    def test_scenario_c_hsm_parameter_count(self):
        # Scenario C: HSM parameter count remains identical to source template
        camp = frappe.get_doc({
            "doctype": "TAP Campaign",
            "campaign_name": "Test HSM count",
            "targeting_type": "Single School",
            "school_name": "Test School 1",
            "template": "test_sync_2",
            # Inject a bad message template manually (bypassing save logic to simulate DB bad state)
            "message_template": "Bad template",
            "send_date": now_datetime(),
            "status": "Draft"
        })
        # If we insert it normally, it gets fixed. Let's do it normally.
        camp.insert(ignore_permissions=True)
        camp.reload()

        # Verify the parameter count extraction
        text = _get_template_text(camp)
        matches = re.findall(r'\{\{(\d+)\}\}', text)
        num_vars = max(map(int, matches)) if matches else 0
        
        self.assertEqual(num_vars, 2)

if __name__ == "__main__":
    unittest.main()
