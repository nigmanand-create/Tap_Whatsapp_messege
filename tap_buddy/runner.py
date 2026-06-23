import frappe
from tap_buddy.tasks.scheduler import _dispatch_flow_campaign
from unittest.mock import MagicMock

def run():
    print("--- E2E Flow Dispatch Verification ---")
    
    # Target Group
    group_id = "WAG-12125"
    wag = frappe.get_doc("WhatsApp Group", group_id)
    print(f"Target Group: {wag.name} (glific_group_id: {wag.glific_group_id})")
    
    # Mock Campaign
    campaign = MagicMock()
    campaign.name = "CAMP-E2E"
    campaign.glific_flow = "40067"
    
    # Mock Recipient
    recipient = MagicMock()
    recipient.name = "REC-E2E"
    recipient.whatsapp_group = wag.name
    recipient.school = None
    recipient.phone = None
    
    # Mock Client
    client = MagicMock()
    client.start_group_flow.return_value = {"success": True}
    
    # Mock DB write
    original_set_value = frappe.db.set_value
    def mock_set_value(doctype, name, fieldname_or_dict, value=None):
        if doctype == "Campaign Recipient":
            print(f"DB Update [{doctype} {name}]: {fieldname_or_dict}")
        try:
            return original_set_value(doctype, name, fieldname_or_dict, value)
        except Exception:
            pass
            
    frappe.db.set_value = mock_set_value
    
    # Execute
    print(f"\nDispatching Flow {campaign.glific_flow} to Recipient via Group {wag.name}...")
    try:
        _dispatch_flow_campaign(client, campaign, recipient)
    except Exception as e:
        print(f"Exception: {e}")
        
    print(f"\nClient Start Group Flow Calls:")
    for call in client.start_group_flow.call_args_list:
        print(f"  {call}")

    # Restore
    frappe.db.set_value = original_set_value

