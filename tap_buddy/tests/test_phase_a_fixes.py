import frappe
import unittest
from unittest.mock import patch, MagicMock

from tap_buddy.api.webhook import handle as webhook_handle
from tap_buddy.api.lms_webhook import handle as lms_webhook_handle
from tap_buddy.services.lms_automation_engine import dispatch_reminder

class TestPhaseABugFixes(unittest.TestCase):
    
    @patch("tap_buddy.api.webhook.frappe.request")
    @patch("tap_buddy.api.webhook.frappe.get_single")
    @patch("tap_buddy.api.webhook.buffer_webhook_payload")
    def test_glific_webhook_hmac_enforced(self, mock_buffer, mock_get_single, mock_request):
        # Setup mock settings with a secret
        mock_settings = MagicMock()
        mock_settings.webhook_enabled = 1
        mock_settings.webhook_secret = "my_secret"
        mock_settings.webhook_signature_header = "X-Glific-Signature"
        mock_get_single.return_value = mock_settings
        
        # Test 1: Missing signature raises error
        mock_request.get_data.return_value = '{"test": "data"}'
        
        with patch("tap_buddy.api.webhook.frappe.get_request_header", return_value=None):
            with self.assertRaises(frappe.exceptions.ValidationError): # Assuming frappe.throw raises ValidationError
                try:
                    webhook_handle()
                except Exception as e:
                    if "Missing webhook signature header" in str(e):
                        raise frappe.exceptions.ValidationError(e)
                    raise e
                    
        # Test 2: Invalid signature raises error
        with patch("tap_buddy.api.webhook.frappe.get_request_header", return_value="sha256=invalid_hash"):
            with self.assertRaises(frappe.exceptions.ValidationError):
                try:
                    webhook_handle()
                except Exception as e:
                    if "Invalid webhook signature" in str(e):
                        raise frappe.exceptions.ValidationError(e)
                    raise e

    @patch("tap_buddy.services.lms_automation_engine.GlificClient")
    @patch("tap_buddy.services.lms_automation_engine.frappe.get_value")
    @patch("tap_buddy.services.lms_automation_engine._log_reminder")
    def test_dispatch_reminder_resolves_template_id(self, mock_log, mock_get_value, mock_client_class):
        # Setup mocks
        mock_get_value.return_value = 999  # Simulated database ID
        
        mock_client_instance = MagicMock()
        mock_client_instance.send_hsm_message.return_value = {"id": "msg_123"}
        mock_client_class.return_value = mock_client_instance
        
        # Call dispatch
        result = dispatch_reminder(
            student_id="ST123",
            student_name="John Doe",
            phone="919999999999",
            reminder_type="ASSIGNMENT_DUE_SOON",
            dedup_key="test_dedup_1"
        )
        
        # Assertions
        self.assertEqual(result, "sent")
        
        # Verify frappe.get_value was called to fetch the ID
        mock_get_value.assert_called_with(
            "WhatsApp Template",
            {"glific_shortcode": "pta_meeting_alert_v2"},
            "glific_db_id"
        )
        
        # Verify the numeric ID was passed to the client
        mock_client_instance.send_hsm_message.assert_called_once()
        call_kwargs = mock_client_instance.send_hsm_message.call_args[1]
        self.assertEqual(call_kwargs["template_id"], 999)
