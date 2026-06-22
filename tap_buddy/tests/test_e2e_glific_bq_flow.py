import json
from unittest.mock import patch, MagicMock
import pytest

import frappe
from tap_buddy.api.glific_bq_webhook import handle

class TestE2EGlificBQWebhookFlow:
    """
    End-to-End test simulating the complete data flow:
    1. Glific Flow Webhook Node triggers POST request.
    2. Webhook Endpoint validates secret and maps resource.
    3. TAP Buddy calls BigQuery (execute_tvf).
    4. BigQuery returns rows.
    5. Webhook returns rows[0] as a flat JSON dictionary suitable for Flow Variables.
    """

    @pytest.fixture(autouse=True)
    def setup_frappe(self):
        # Set up a test context for Frappe local
        frappe.local.response = frappe._dict()
        yield
        # Cleanup
        frappe.local.response = {}

    @patch("tap_buddy.api.glific_bq_webhook.frappe.get_single")
    @patch("tap_buddy.api.glific_bq_webhook.execute_tvf")
    def test_end_to_end_flow(self, mock_execute_tvf, mock_get_single):
        # Ensure a secret is configured in Settings mock
        settings_mock = MagicMock()
        settings_mock.get_password.return_value = "e2e_secure_secret"
        settings_mock.webhook_secret = "e2e_secure_secret"
        mock_get_single.return_value = settings_mock
        # 1. Glific Flow: The payload sent by the Webhook Node
        glific_payload = {
            "secret": "e2e_secure_secret",
            "resource": "attendance_context",
            "contact": {
                "name": "Test User",
                "phone": "918888888888"
            },
            "parameters": {
                "month": "October"
            }
        }
        
        # Mock the raw request
        mock_req = MagicMock()
        mock_req.get_data.return_value = json.dumps(glific_payload)
        frappe.request = mock_req

        # 2. BigQuery execution mock (simulates data returned from BQ)
        mock_execute_tvf.return_value = [
            {
                "student_name": "Test User",
                "attendance_percentage": 92.5,
                "days_absent": 2,
                "last_active": "2026-10-15"
            }
        ]

        # 3. TAP Buddy handles the request
        response = handle()

        # 4. Verify BigQuery was called with the mapped TVF and merged parameters
        mock_execute_tvf.assert_called_once_with(
            "get_attendance_context_v1",  # 'attendance_context' mapped to TVF
            {
                "month": "October",
                "phone": "918888888888"  # phone merged from contact
            },
            mock_mode=False
        )

        # 5. Verify the JSON Response is completely flat and valid for Flow Variables
        assert isinstance(response, dict)
        assert response.get("student_name") == "Test User"
        assert response.get("attendance_percentage") == 92.5
        assert response.get("days_absent") == 2
        assert response.get("last_active") == "2026-10-15"

        # Glific Flow Variables will now be available as:
        # @webhook.student_name
        # @webhook.attendance_percentage
        # @webhook.days_absent
        # @webhook.last_active
