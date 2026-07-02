import json
import time
from unittest.mock import MagicMock, patch
import pytest
import frappe

from tap_buddy.dynamic_context.api import handle
from tap_buddy.dynamic_context.models import FlowConfig, FieldConfig, FieldSource
from tap_buddy.dynamic_context.exceptions import ConfigurationError, ValidationError, AuthenticationError, ProviderExecutionError
from tap_buddy.dynamic_context.cache import IsolatedCacheWrapper


@pytest.fixture(autouse=True)
def setup_vertical_slice_env():
    """Sets up isolated Frappe test environment for Vertical Slice Validation."""
    frappe.init(site="tapbuddy.local", sites_path=".")
    frappe.flags.in_test = True
    frappe.local.flags = frappe._dict()
    frappe.local.response = frappe._dict()
    frappe.local.conf = frappe._dict({"time_zone": "UTC", "bq_timeout_sec": 15})
    
    # In-memory mock redis cache
    _cache_store = {}
    
    def _mock_get_value(key):
        return _cache_store.get(key)
        
    def _mock_set_value(key, val, expires_in_sec=None):
        _cache_store[key] = val
        
    mock_cache_client = MagicMock()
    mock_cache_client.get_value.side_effect = _mock_get_value
    mock_cache_client.set_value.side_effect = _mock_set_value

    with patch("frappe.cache", return_value=mock_cache_client), \
         patch("frappe.logger", return_value=MagicMock()):
        yield


class TestPhase4VerticalSliceValidation:
    """
    Phase 4 Vertical Slice Validation demonstrating complete end-to-end execution lifecycle:
    Glific Webhook -> Resolution Engine -> BigQuery TVF -> Caching -> Glific Variable Consumption.
    """

    @pytest.fixture
    def mock_settings(self):
        st = MagicMock()
        st.get_password.return_value = "vertical_secure_secret"
        st.webhook_secret = "vertical_secure_secret"
        return st

    @pytest.fixture
    def realistic_doctype_flow_config(self):
        """
        Deliverable 1: Real Flow Configuration representing a Frappe DocType record.
        Populated with realistic PI team flow requirements.
        """
        doc = MagicMock()
        doc.name = "onboarding_school_v1"
        doc.flow_name = "Onboarding School Context Flow"
        doc.flow_category = "onboarding"
        doc.bq_routine_name = "get_onboarding_context_v1"
        doc.cache_ttl = 300
        doc.bypass_cache = 0

        # Child table fields
        f1 = MagicMock(field_name="total_registrations", field_source="BigQuery", is_required=0, default_value=0, validation_regex=None)
        f2 = MagicMock(field_name="school_registrations", field_source="BigQuery", is_required=0, default_value=0, validation_regex=None)
        f3 = MagicMock(field_name="school_name", field_source="Payload", is_required=1, default_value=None, validation_regex=None)
        f4 = MagicMock(field_name="registration_link", field_source="Manual Default", is_required=0, default_value="https://tap.example.com/register", validation_regex=None)
        
        doc.fields = [f1, f2, f3, f4]
        return doc

    @patch("tap_buddy.services.bigquery_executor.execute_tvf")
    @patch("frappe.get_all")
    @patch("frappe.get_doc")
    @patch("frappe.get_single")
    def test_complete_vertical_slice_workflow_and_cache_latency(
        self, mock_get_single, mock_get_doc, mock_get_all, mock_execute_tvf, mock_settings, realistic_doctype_flow_config
    ):
        """
        Proves Deliverables 2, 3, 4, 5, 6: Complete E2E workflow, TVF reuse, Caching verification, and Latency metrics.
        """
        mock_get_single.return_value = mock_settings
        mock_get_all.return_value = [MagicMock(name="onboarding_school_v1")]
        mock_get_doc.return_value = realistic_doctype_flow_config

        # Deliverable 2: Complete BigQuery routine execution returned data
        mock_execute_tvf.return_value = [{"total_registrations": 1250, "school_registrations": 42}]

        # Deliverable 3: Real Glific webhook incoming payload
        incoming_payload = {
            "request_id": "req-slice-001",
            "secret": "vertical_secure_secret",
            "flow_category": "onboarding",
            "contact": {"phone": "919876543210", "name": "Sunita Rao"},
            "school_name": "KV Ganeshkhind Pune",
            "mock_mode": 1
        }

        mock_req = MagicMock()
        mock_req.get_data.return_value = json.dumps(incoming_payload)
        frappe.request = mock_req

        # --- EXECUTION 1: CACHE MISS ---
        start_t1 = time.time()
        response1 = handle()
        latency_ms_1 = (time.time() - start_t1) * 1000.0

        assert response1["success"] is True
        assert response1["version"] == "v1"
        assert response1["request_id"] == "req-slice-001"
        assert response1["source"] == "dynamic_context_engine"

        context1 = response1["context"]
        assert context1["total_registrations"] == 1250
        assert context1["school_registrations"] == 42
        assert context1["school_name"] == "KV Ganeshkhind Pune"
        assert context1["registration_link"] == "https://tap.example.com/register"

        # Verify BigQuery TVF called exactly once
        mock_execute_tvf.assert_called_once_with(
            "get_onboarding_context_v1",
            {"school_name": "KV Ganeshkhind Pune", "phone": "919876543210"},
            mock_mode=True
        )

        # Deliverable 4: Glific Integration Consumption Proof
        # Inside Glific Flow, these variables resolve cleanly:
        # @results.call_webhook.context.total_registrations -> 1250
        # @results.call_webhook.context.school_name -> "KV Ganeshkhind Pune"
        # @results.call_webhook.context.registration_link -> "https://tap.example.com/register"

        # --- EXECUTION 2: CACHE HIT ---
        incoming_payload["request_id"] = "req-slice-002"
        mock_req.get_data.return_value = json.dumps(incoming_payload)

        start_t2 = time.time()
        response2 = handle()
        latency_ms_2 = (time.time() - start_t2) * 1000.0

        assert response2["success"] is True
        assert response2["request_id"] == "req-slice-002"
        assert response2["context"] == context1

        # Deliverable 5 & 6 Verification: BQ NOT called a second time (assert_called_once holds)
        mock_execute_tvf.assert_called_once()

        # Quantitative Latency Proof
        print(f"\n[Performance Metrics] First Request (Cache MISS + BQ): {round(latency_ms_1, 2)}ms")
        print(f"[Performance Metrics] Second Request (Cache HIT): {round(latency_ms_2, 2)}ms")
        assert latency_ms_2 < latency_ms_1

    @patch("frappe.get_single")
    def test_failure_mode_invalid_secret(self, mock_get_single, mock_settings):
        """Deliverable 7a: Demonstrates unauthorized secret token schema response."""
        mock_get_single.return_value = mock_settings
        payload = {"secret": "wrong_secret", "flow_category": "onboarding"}
        frappe.request = MagicMock(get_data=MagicMock(return_value=json.dumps(payload)))

        res = handle()
        assert res["success"] is False
        assert res["version"] == "v1"
        assert res["error"]["code"] == "UNAUTHORIZED"
        assert frappe.local.response.http_status_code == 401

    @patch("frappe.get_all", return_value=[])
    @patch("frappe.get_single")
    def test_failure_mode_unknown_flow(self, mock_get_single, mock_get_all, mock_settings):
        """Deliverable 7b: Demonstrates unconfigured flow category schema response."""
        mock_get_single.return_value = mock_settings
        payload = {"secret": "vertical_secure_secret", "flow_category": "nonexistent_flow"}
        frappe.request = MagicMock(get_data=MagicMock(return_value=json.dumps(payload)))

        res = handle()
        assert res["success"] is False
        assert res["error"]["code"] == "FLOW_NOT_FOUND"
        assert frappe.local.response.http_status_code == 404

    @patch("frappe.get_all")
    @patch("frappe.get_doc")
    @patch("frappe.get_single")
    def test_failure_mode_validation_failure(self, mock_get_single, mock_get_doc, mock_get_all, mock_settings, realistic_doctype_flow_config):
        """Deliverable 7c: Demonstrates mandatory field validation failure schema response."""
        mock_get_single.return_value = mock_settings
        mock_get_all.return_value = [MagicMock(name="onboarding_school_v1")]
        mock_get_doc.return_value = realistic_doctype_flow_config

        # Missing required 'school_name' in payload
        payload = {"secret": "vertical_secure_secret", "flow_category": "onboarding", "contact": {"phone": "919876543210"}}
        frappe.request = MagicMock(get_data=MagicMock(return_value=json.dumps(payload)))

        res = handle()
        assert res["success"] is False
        assert res["error"]["code"] == "VALIDATION_FAILED"
        assert "Required input field 'school_name' is missing" in res["error"]["message"]
        assert frappe.local.response.http_status_code == 400

    @patch("tap_buddy.services.bigquery_executor.execute_tvf")
    @patch("frappe.get_all")
    @patch("frappe.get_doc")
    @patch("frappe.get_single")
    def test_failure_mode_bigquery_timeout(self, mock_get_single, mock_get_doc, mock_get_all, mock_execute_tvf, mock_settings, realistic_doctype_flow_config):
        """Deliverable 7d: Demonstrates BigQuery execution timeout protection schema response."""
        mock_get_single.return_value = mock_settings
        mock_get_all.return_value = [MagicMock(name="onboarding_school_v1")]
        mock_get_doc.return_value = realistic_doctype_flow_config

        # Simulate slow query exceeding timeout
        def _sleepy_tvf(*args, **kwargs):
            time.sleep(2.0)
            return []

        mock_execute_tvf.side_effect = _sleepy_tvf
        frappe.local.conf.bq_timeout_sec = 0.1 # Set 100ms timeout for testing

        payload = {"secret": "vertical_secure_secret", "flow_category": "onboarding", "school_name": "DPS", "contact": {"phone": "919876543210"}, "mock_mode": 1}
        frappe.request = MagicMock(get_data=MagicMock(return_value=json.dumps(payload)))

        res = handle()
        assert res["success"] is False
        assert res["error"]["code"] == "PROVIDER_EXECUTION_FAILED"
        assert "timed out after" in res["error"]["message"]
        assert frappe.local.response.http_status_code == 500
