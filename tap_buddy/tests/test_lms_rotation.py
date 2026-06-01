import unittest
from unittest.mock import patch, MagicMock
import frappe
from tap_buddy.services.lms_client import LMSClient, LMSAPIError
import requests

class TestLMSRotation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Ensure LMS Integration Settings exists
        if not frappe.db.exists("DocType", "LMS Integration Settings"):
            return
        settings = frappe.get_doc("LMS Integration Settings", "LMS Integration Settings")
        settings.lms_username = "test_user@evalix.xyz"
        settings.lms_password = "test_password"
        settings.lms_base_url = "http://mock-lms.local"
        settings.lms_api_key = "old_key:old_secret"
        settings.save()
        frappe.db.commit()

    @patch('requests.Session.request')
    @patch('requests.Session.post')
    @patch('requests.Session.get')
    def test_auto_rotation_on_401(self, mock_get, mock_post, mock_request):
        # 1. First request returns 401
        # 2. After rotation, second request returns 200
        mock_401 = MagicMock()
        mock_401.status_code = 401
        mock_401.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized", response=mock_401)
        mock_401.text = "Unauthorized"

        mock_200 = MagicMock()
        mock_200.status_code = 200
        mock_200.text = '{"data": [{"name": "student1"}]}'
        mock_200.json.return_value = {"data": [{"name": "student1"}]}
        
        mock_request.side_effect = [mock_401, mock_200]

        # Login POST response
        mock_login = MagicMock()
        mock_login.status_code = 200

        # Generate Keys POST response
        mock_keys = MagicMock()
        mock_keys.status_code = 200
        mock_keys.json.return_value = {"message": {"api_secret": "new_secret_123"}}
        
        mock_post.side_effect = [mock_login, mock_keys]

        # User details GET response
        mock_user = MagicMock()
        mock_user.status_code = 200
        mock_user.json.return_value = {"data": {"api_key": "new_key_456"}}
        mock_get.return_value = mock_user

        client = LMSClient()
        client.base_url = "http://mock-lms.local"
        
        result = client.get_students()
        
        # Check that it successfully fetched data after rotation
        self.assertEqual(result["data"][0]["name"], "student1")
        
        # Check that post was called twice (login, generate_keys)
        self.assertEqual(mock_post.call_count, 2)
        
        # Check DB was updated
        settings = frappe.get_doc("LMS Integration Settings", "LMS Integration Settings")
        new_token = settings.get_password("lms_api_key")
        self.assertEqual(new_token, "new_key_456:new_secret_123")

