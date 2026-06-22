import json
import unittest
from unittest.mock import patch
import datetime
import decimal
import frappe
from tap_buddy.services.bigquery_executor import JSONEncoderCustom, execute_tvf, RESOURCE_NAME_REGEX
from tap_buddy.api.bigquery import get_cache_key

class TestBigQueryProxy(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create or update Settings
        if not frappe.db.exists("DocType", "TAP BigQuery Settings"):
            # Should have been created by module scaffolding, but safe guard
            pass
        else:
            settings = frappe.get_single("TAP BigQuery Settings")
            settings.enabled = 1
            settings.project_id = "test-project"
            settings.dataset_id = "test_dataset"
            settings.service_account_json = '{"type": "service_account"}'
            settings.save(ignore_permissions=True)

    def test_resource_name_validation(self):
        """Ensure SQL injection attempts are blocked."""
        self.assertTrue(bool(RESOURCE_NAME_REGEX.match("get_student_v1")))
        self.assertTrue(bool(RESOURCE_NAME_REGEX.match("test_routine")))
        self.assertFalse(bool(RESOURCE_NAME_REGEX.match("drop table;")))
        self.assertFalse(bool(RESOURCE_NAME_REGEX.match("routine()")))
        
        with self.assertRaises(frappe.exceptions.ValidationError):
            execute_tvf("invalid name;", {}, mock_mode=True)

    def test_json_serialization(self):
        """Ensure BQ native types convert to strings safely."""
        mock_row = {
            "name": "Test",
            "created_at": datetime.datetime(2026, 6, 18, 12, 0, 0),
            "birth_date": datetime.date(2000, 1, 1),
            "score": decimal.Decimal("95.5")
        }
        json_str = json.dumps(mock_row, cls=JSONEncoderCustom)
        parsed = json.loads(json_str)
        self.assertEqual(parsed["created_at"], "2026-06-18T12:00:00")
        self.assertEqual(parsed["birth_date"], "2000-01-01")
        self.assertEqual(parsed["score"], 95.5)

    def test_deterministic_cache_key(self):
        """Ensure identical parameter content yields the same hash regardless of order."""
        params1 = {"phone": "123", "course": "MATH"}
        params2 = {"course": "MATH", "phone": "123"}
        
        key1 = get_cache_key("dataset", "routine", params1)
        key2 = get_cache_key("dataset", "routine", params2)
        
        self.assertEqual(key1, key2)

    def test_mock_execution(self):
        """Test the mock mode of the execution proxy."""
        params = {"id": 5}
        result = execute_tvf("get_student", params, mock_mode=True)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["mocked"])
        self.assertEqual(result[0]["resource"], "get_student")
        
        # Verify it serialized parameters correctly
        payload_parsed = json.loads(result[0]["payload"])
        self.assertEqual(payload_parsed["id"], 5)

    @patch("tap_buddy.services.bigquery_executor.service_account.Credentials.from_service_account_info")
    @patch("tap_buddy.services.bigquery_executor.bigquery.Client")
    @patch("tap_buddy.services.bigquery_executor.frappe.get_single")
    def test_credentials_raw_json(self, mock_get_single, mock_bq_client, mock_from_sa):
        """Test raw JSON string parsing."""
        valid_json = '{"project_id": "test", "private_key": "key", "client_email": "email"}'
        
        mock_settings = unittest.mock.MagicMock()
        mock_settings.enabled = 1
        mock_settings.project_id = "test_project"
        mock_settings.get_password.return_value = valid_json
        mock_get_single.return_value = mock_settings
        
        from tap_buddy.services.bigquery_executor import get_bq_client
        get_bq_client(mock_mode=False)
        
        mock_from_sa.assert_called_once()
        args = mock_from_sa.call_args[0][0]
        self.assertEqual(args["project_id"], "test")

    @patch("tap_buddy.services.bigquery_executor.service_account.Credentials.from_service_account_info")
    @patch("tap_buddy.services.bigquery_executor.bigquery.Client")
    @patch("os.path.exists")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data='{"project_id": "file_test", "private_key": "key", "client_email": "email"}')
    @patch("tap_buddy.services.bigquery_executor.frappe.get_single")
    def test_credentials_file_path(self, mock_get_single, mock_file, mock_exists, mock_bq_client, mock_from_sa):
        """Test reading credentials from a valid file path."""
        mock_exists.return_value = True
        
        mock_settings = unittest.mock.MagicMock()
        mock_settings.enabled = 1
        mock_settings.project_id = "test_project"
        mock_settings.get_password.return_value = "/path/to/creds.json"
        mock_get_single.return_value = mock_settings
        
        from tap_buddy.services.bigquery_executor import get_bq_client
        get_bq_client(mock_mode=False)
        
        mock_file.assert_called_once_with("/path/to/creds.json", "r")
        mock_from_sa.assert_called_once()
        args = mock_from_sa.call_args[0][0]
        self.assertEqual(args["project_id"], "file_test")

    @patch("os.path.exists")
    @patch("tap_buddy.services.bigquery_executor.frappe.get_single")
    def test_credentials_missing_file(self, mock_get_single, mock_exists):
        """Test error when file is missing."""
        mock_exists.return_value = False
        
        mock_settings = unittest.mock.MagicMock()
        mock_settings.enabled = 1
        mock_settings.project_id = "test_project"
        mock_settings.get_password.return_value = "/invalid/path.json"
        mock_get_single.return_value = mock_settings
        
        from tap_buddy.services.bigquery_executor import get_bq_client
        
        with self.assertRaises(frappe.exceptions.ValidationError) as context:
            get_bq_client(mock_mode=False)
            
        self.assertIn("Service Account file not found", str(context.exception))

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=unittest.mock.mock_open, read_data='{invalid_json')
    @patch("tap_buddy.services.bigquery_executor.frappe.get_single")
    def test_credentials_invalid_json(self, mock_get_single, mock_file, mock_exists):
        """Test error when file contains invalid JSON."""
        mock_exists.return_value = True
        
        mock_settings = unittest.mock.MagicMock()
        mock_settings.enabled = 1
        mock_settings.project_id = "test_project"
        mock_settings.get_password.return_value = "/path/to/bad.json"
        mock_get_single.return_value = mock_settings
        
        from tap_buddy.services.bigquery_executor import get_bq_client
        
        with self.assertRaises(frappe.exceptions.ValidationError) as context:
            get_bq_client(mock_mode=False)
            
        self.assertIn("Invalid Service Account JSON in file", str(context.exception))

    @patch("tap_buddy.services.bigquery_executor.frappe.get_single")
    def test_credentials_missing_fields(self, mock_get_single):
        """Test error when JSON is missing required BigQuery fields."""
        incomplete_json = '{"project_id": "test"}'
        
        mock_settings = unittest.mock.MagicMock()
        mock_settings.enabled = 1
        mock_settings.project_id = "test_project"
        mock_settings.get_password.return_value = incomplete_json
        mock_get_single.return_value = mock_settings
        
        from tap_buddy.services.bigquery_executor import get_bq_client
        
        with self.assertRaises(frappe.exceptions.ValidationError) as context:
            get_bq_client(mock_mode=False)
            
        self.assertIn("Missing required service account field: private_key", str(context.exception))
