import unittest
from unittest.mock import patch, MagicMock
import datetime
import requests
import frappe

from tap_buddy.services.glific_client import GlificClient, GlificTerminalError
from tap_buddy.tasks.scheduler import check_and_refresh_glific_token

class TestGlificAuthRefresh(unittest.TestCase):
    def setUp(self):
        self.mock_settings = MagicMock()
        self.mock_settings.glific_url = "https://mock.glific.com"
        self.mock_settings.glific_access_token = "old_token"
        self.mock_settings.glific_refresh_token = "old_refresh"
        self.mock_settings.glific_token_refresh_buffer_minutes = 10
        
        future = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
        self.mock_settings.glific_token_expiry = future.isoformat()
        
        self.patcher_settings = patch("tap_buddy.services.glific_client.frappe.get_single", return_value=self.mock_settings)
        self.patcher_settings.start()
        
        # get_safe_password might try to read db
        def _mock_get_safe_password(doc, field):
            return getattr(doc, field, None)
            
        self.patcher_pwd = patch("tap_buddy.services.glific_client.get_safe_password", side_effect=_mock_get_safe_password)
        self.patcher_pwd.start()
        
        # mock frappe.logger to prevent missing handler errors during test
        self.patcher_logger = patch("tap_buddy.services.glific_client.frappe.logger")
        self.patcher_logger.start()

    def tearDown(self):
        self.patcher_settings.stop()
        self.patcher_pwd.stop()
        self.patcher_logger.stop()

    def test_expiry_check_within_buffer(self):
        client = GlificClient()
        # Set expiry to 9 mins from now (within the 10 min buffer)
        client.token_expiry = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=9)).isoformat()
        self.assertTrue(client.should_refresh_token())

    def test_expiry_check_outside_buffer(self):
        client = GlificClient()
        # Set expiry to 11 mins from now (outside the 10 min buffer)
        client.token_expiry = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=11)).isoformat()
        self.assertFalse(client.should_refresh_token())

    @patch("tap_buddy.services.glific_client.GlificClient")
    def test_scheduler_proactive_refresh(self, MockClient):
        client_instance = MockClient.return_value
        check_and_refresh_glific_token()
        client_instance.ensure_valid_token.assert_called_once()

    @patch("tap_buddy.services.glific_client.GlificClient._perform_token_refresh")
    def test_401_retry_success(self, mock_refresh):
        client = GlificClient()
        client.ensure_valid_token = MagicMock()
        
        mock_response_401 = MagicMock()
        mock_response_401.status_code = 401
        
        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        
        mock_func = MagicMock(side_effect=[mock_response_401, mock_response_200])
        
        result = client._with_auth_retry(mock_func)
        
        self.assertEqual(result.status_code, 200)
        self.assertEqual(mock_func.call_count, 2)
        mock_refresh.assert_called_once()

    @patch("tap_buddy.services.glific_client.requests.post")
    def test_unrecoverable_refresh_failure(self, mock_post):
        client = GlificClient()
        
        mock_response_400 = MagicMock()
        mock_response_400.status_code = 400
        mock_response_400.raise_for_status.side_effect = requests.exceptions.HTTPError("400 Client Error")
        mock_post.return_value = mock_response_400
        
        with self.assertRaises(GlificTerminalError):
            client._perform_token_refresh()
            
        self.assertIsNone(client.refresh_token)
        # We no longer clear it from settings on terminal failure
        self.assertEqual(self.mock_settings.db_set.call_count, 0)

    @patch("tap_buddy.services.glific_client.acquire_lock")
    @patch("tap_buddy.services.glific_client.time.sleep")
    @patch("tap_buddy.services.glific_client.GlificClient._reload_credentials_from_db")
    def test_concurrent_worker_lock_timeout(self, mock_reload, mock_sleep, mock_lock):
        client = GlificClient()
        # Force it to need refresh
        client.token_expiry = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)).isoformat()
        
        # Lock never acquired
        mock_lock.return_value = False
        
        client.ensure_valid_token()
        
        self.assertEqual(mock_lock.call_count, 5)
        self.assertEqual(mock_sleep.call_count, 5)
        mock_reload.assert_called_once()
