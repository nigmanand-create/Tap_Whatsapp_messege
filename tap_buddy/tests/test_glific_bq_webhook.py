import json
from unittest.mock import MagicMock, patch
import pytest

import frappe
from tap_buddy.api.glific_bq_webhook import handle


@pytest.fixture
def mock_request():
    mock_req = MagicMock()
    mock_req.get_data = MagicMock(return_value="{}")
    frappe.request = mock_req
    return mock_req

@pytest.fixture
def mock_response():
    mock_res = MagicMock()
    frappe.local.response = mock_res
    return mock_res

@pytest.fixture
def mock_settings():
    with patch("tap_buddy.api.glific_bq_webhook.frappe.get_single") as mock_get_single:
        settings_mock = MagicMock()
        settings_mock.get_password.return_value = "secret123"
        settings_mock.webhook_secret = "secret123"
        mock_get_single.return_value = settings_mock
        yield mock_get_single

@pytest.fixture
def mock_execute_tvf():
    with patch("tap_buddy.api.glific_bq_webhook.execute_tvf") as m:
        yield m

class TestGlificBQWebhook:

    def test_valid_request(self, mock_request, mock_response, mock_settings, mock_execute_tvf):
        payload = {
            "secret": "secret123",
            "resource": "student_context",
            "contact": {
                "phone": "919999999999"
            }
        }
        mock_request.get_data.return_value = json.dumps(payload)
        
        # Mock rows returned by BigQuery
        mock_execute_tvf.return_value = [{"student_name": "Rahul", "attendance": 87}]

        response = handle()

        # Check successful response
        assert response == {"student_name": "Rahul", "attendance": 87}
        
        # Check execute_tvf was called correctly
        mock_execute_tvf.assert_called_once_with(
            "get_student_context_v1", 
            {"phone": "919999999999"}, 
            mock_mode=False
        )

    def test_invalid_secret(self, mock_request, mock_response, mock_settings):
        payload = {
            "secret": "wrong_secret",
            "resource": "student_context",
            "contact": {"phone": "919999999999"}
        }
        mock_request.get_data.return_value = json.dumps(payload)

        response = handle()
        
        assert mock_response.http_status_code == 401
        assert "Unauthorized" in response["error"]

    def test_missing_phone(self, mock_request, mock_response, mock_settings):
        payload = {
            "secret": "secret123",
            "resource": "student_context",
            "contact": {}
        }
        mock_request.get_data.return_value = json.dumps(payload)

        response = handle()

        assert mock_response.http_status_code == 400
        assert "Missing 'contact.phone'" in response["error"]

    def test_invalid_resource(self, mock_request, mock_response, mock_settings):
        payload = {
            "secret": "secret123",
            "resource": "nonexistent_tvf",
            "contact": {"phone": "919999999999"}
        }
        mock_request.get_data.return_value = json.dumps(payload)

        response = handle()

        assert mock_response.http_status_code == 403
        assert "not whitelisted" in response["error"]

    def test_bigquery_failure_mapping(self, mock_request, mock_response, mock_settings, mock_execute_tvf):
        payload = {
            "secret": "secret123",
            "resource": "student_context",
            "contact": {"phone": "919999999999"}
        }
        mock_request.get_data.return_value = json.dumps(payload)

        # Simulate BigQuery NotFound exception
        class NotFound(Exception):
            pass

        mock_execute_tvf.side_effect = NotFound("Table not found")

        response = handle()

        assert mock_response.http_status_code == 404
        assert "Resource does not exist" in response["error"]

    def test_empty_result_handling(self, mock_request, mock_response, mock_settings, mock_execute_tvf):
        payload = {
            "secret": "secret123",
            "resource": "student_context",
            "contact": {"phone": "919999999999"}
        }
        mock_request.get_data.return_value = json.dumps(payload)
        
        # Mock empty list returned by BigQuery
        mock_execute_tvf.return_value = []

        response = handle()

        assert response == {}
