import json
import unittest
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
