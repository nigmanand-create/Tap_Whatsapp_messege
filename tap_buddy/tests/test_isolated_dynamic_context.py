import json
import os
from unittest.mock import MagicMock, patch
import pytest
import frappe

from tap_buddy.dynamic_context.api import handle
from tap_buddy.dynamic_context.builder import ContextBuilder
from tap_buddy.dynamic_context.providers.config import JsonFileConfigProvider
from tap_buddy.dynamic_context.registry import FlowRegistry
from tap_buddy.dynamic_context.cache import IsolatedCacheWrapper
from tap_buddy.dynamic_context.validators import PayloadValidator
from tap_buddy.dynamic_context.models import FlowConfig, FieldConfig, FieldSource
from tap_buddy.dynamic_context.exceptions import ValidationError, ConfigurationError


@pytest.fixture(autouse=True)
def setup_frappe_local():
    sites_path = "sites" if os.path.exists("sites/tapbuddy.local") else "."
    frappe.init(site="tapbuddy.local", sites_path=sites_path)
    frappe.local.flags = frappe._dict()
    frappe.local.response = frappe._dict()
    with patch("frappe.get_all", side_effect=Exception("Mock DB lookup failed")), \
         patch("frappe.cache", return_value=MagicMock(get_value=MagicMock(return_value=None))), \
         patch("frappe.logger", return_value=MagicMock()):
        yield


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
    with patch("tap_buddy.dynamic_context.api.frappe.get_single") as mock_get_single:
        settings_mock = MagicMock()
        settings_mock.get_password.return_value = "test_secret"
        settings_mock.webhook_secret = "test_secret"
        mock_get_single.return_value = settings_mock
        yield mock_get_single


class TestConfigProvider:
    def test_builtin_categories_coverage(self):
        prv = JsonFileConfigProvider()
        categories = ["priority", "onboarding", "program_announcements", "engagement", "feedback", "celebratory"]
        for cat in categories:
            cfg = prv.get_flow_config(category_fallback=cat)
            assert cfg is not None
            assert cfg.category == cat
            assert len(cfg.fields) > 0

    def test_master_flow_ids_resolution(self):
        prv = JsonFileConfigProvider()
        reg = FlowRegistry(config_provider=prv)
        master_flows = [
            ("builtin_priority", "priority"),
            ("builtin_onboarding", "onboarding"),
            ("builtin_program_announcements", "program_announcements"),
            ("builtin_engagement", "engagement"),
            ("builtin_feedback", "feedback"),
            ("builtin_celebratory", "celebratory"),
        ]
        for flow_id, expected_cat in master_flows:
            cfg = reg.get_flow_config(flow_id=flow_id)
            assert cfg is not None, f"Flow ID '{flow_id}' failed to resolve in FlowRegistry"
            assert cfg.flow_id == flow_id
            assert cfg.category == expected_cat
            assert cfg.cache_ttl == 300
            assert cfg.bypass_cache is False


class TestDataProviders:
    @patch("tap_buddy.services.bigquery_executor.execute_tvf")
    def test_bigquery_provider_batching(self, mock_execute_tvf):
        mock_execute_tvf.return_value = [{"total_registrations": 100, "school_registrations": 50, "school_name": "ABC"}]
        
        prv = JsonFileConfigProvider()
        reg = FlowRegistry(config_provider=prv)
        builder = ContextBuilder(registry=reg)

        payload = {
            "flow_category": "onboarding",
            "contact": {"phone": "919876543210"},
            "mock_mode": 0
        }

        # Build context
        result = builder.build_context(payload)

        # Confirm execute_tvf was called EXACTLY once despite multiple BQ fields on onboarding flow
        mock_execute_tvf.assert_called_once()
        assert result["total_registrations"] == 100


class TestPayloadValidator:
    def test_required_field_enforcement(self):
        cfg = FlowConfig(
            flow_id="test_req",
            flow_name="Test Required",
            category="custom",
            fields=(FieldConfig("school_id", FieldSource.PAYLOAD, required=True),)
        )
        with pytest.raises(ValidationError, match="Required input field 'school_id' is missing"):
            PayloadValidator.validate_payload(cfg, {"other": "val"})

    def test_regex_validation_enforcement(self):
        cfg = FlowConfig(
            flow_id="test_reg",
            flow_name="Test Regex",
            category="custom",
            fields=(FieldConfig("pincode", FieldSource.PAYLOAD, validation_regex=r"^\d{6}$"),)
        )
        with pytest.raises(ValidationError, match="failed regex validation"):
            PayloadValidator.validate_payload(cfg, {"pincode": "abc12"})


class TestIsolatedCacheWrapper:
    def test_deterministic_key_generation(self):
        key1 = IsolatedCacheWrapper.generate_cache_key("flow1", "919999", {"a": 1, "b": 2}, False)
        key2 = IsolatedCacheWrapper.generate_cache_key("flow1", "919999", {"b": 2, "a": 1}, False)
        assert key1 == key2


class TestDynamicContextAPI:
    def test_api_handle_success_format(self, mock_request, mock_response, mock_settings):
        payload = {
            "secret": "test_secret",
            "flow_category": "priority",
            "state": "Bihar",
            "district": "Patna",
            "zone": "Zone A"
        }
        mock_request.get_data.return_value = json.dumps(payload)
        frappe.flags.in_test = True

        res = handle()
        assert res.get("error") is None, f"Handle failed with: {res}"
        assert res["success"] is True
        assert res["version"] == "v1"
        assert "request_id" in res
        assert res["source"] == "dynamic_context_engine"
        assert "generated_at" in res
        
        # Check context contents
        assert res["context"]["state"] == "Bihar"
        assert res["context"]["zone"] == "Zone A"
