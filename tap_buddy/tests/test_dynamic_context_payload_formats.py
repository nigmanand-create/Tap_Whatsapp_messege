import json
from unittest.mock import MagicMock, patch
import pytest
import frappe

from tap_buddy.dynamic_context.api import handle
from tap_buddy.dynamic_context.builder import ContextBuilder
from tap_buddy.dynamic_context.providers.data import PayloadDataProvider, DefaultDataProvider
from tap_buddy.dynamic_context.providers.config import JsonFileConfigProvider
from tap_buddy.dynamic_context.registry import FlowRegistry
from tap_buddy.dynamic_context.validators import PayloadValidator
from tap_buddy.dynamic_context.models import FlowConfig, FieldConfig, FieldSource, ResolutionContext
from tap_buddy.dynamic_context.exceptions import ValidationError
from tap_buddy.dynamic_context.utils import get_payload_value, extract_params


@pytest.fixture(autouse=True)
def setup_frappe_local():
    frappe.init(site="tapbuddy.local", sites_path=".")
    frappe.local.flags = frappe._dict()
    frappe.local.response = frappe._dict()
    with patch("frappe.get_all", side_effect=Exception("Mock DB lookup failed")), \
         patch("frappe.cache", return_value=MagicMock(get_value=MagicMock(return_value=None))), \
         patch("frappe.logger", return_value=MagicMock()):
        yield


class TestPayloadAccessUtils:
    def test_get_payload_value_root_precedence(self):
        payload = {
            "key": "root_val",
            "parameters": {"key": "param_val", "param_only": "param_val2"}
        }
        assert get_payload_value(payload, "key") == "root_val"
        assert get_payload_value(payload, "param_only") == "param_val2"
        assert get_payload_value(payload, "non_existent", "default") == "default"

    def test_extract_params_merging(self):
        payload = {
            "flow_id": "f1",
            "root_param": "root1",
            "shared_param": "from_root",
            "parameters": {"shared_param": "from_param", "nested_param": "nested1"}
        }
        extracted = extract_params(payload)
        assert extracted["root_param"] == "root1"
        assert extracted["nested_param"] == "nested1"
        assert extracted["shared_param"] == "from_root"
        assert "flow_id" not in extracted


class TestValidatorPayloadFormats:
    def test_validate_payload_root_format(self):
        cfg = FlowConfig(
            flow_id="test_flow",
            flow_name="Test Flow",
            category="custom",
            fields=(FieldConfig("student_id", FieldSource.PAYLOAD, required=True, validation_regex=r"^\d{4}$"),)
        )
        # Should succeed with field at root level
        PayloadValidator.validate_payload(cfg, {"student_id": "1234"})

    def test_validate_payload_parameters_format(self):
        cfg = FlowConfig(
            flow_id="test_flow",
            flow_name="Test Flow",
            category="custom",
            fields=(FieldConfig("student_id", FieldSource.PAYLOAD, required=True, validation_regex=r"^\d{4}$"),)
        )
        # Should succeed with field inside parameters dict
        PayloadValidator.validate_payload(cfg, {"parameters": {"student_id": "1234"}})

    def test_validate_payload_missing(self):
        cfg = FlowConfig(
            flow_id="test_flow",
            flow_name="Test Flow",
            category="custom",
            fields=(FieldConfig("student_id", FieldSource.PAYLOAD, required=True),)
        )
        with pytest.raises(ValidationError):
            PayloadValidator.validate_payload(cfg, {"parameters": {"other": "val"}})


class TestProviderPayloadFormats:
    def test_payload_data_provider_formats(self):
        provider = PayloadDataProvider()
        field_cfg = FieldConfig("school_code", FieldSource.PAYLOAD, default_value="default_code")

        ctx_root = ResolutionContext(flow_id="f1", phone="123", raw_payload={"school_code": "SC_ROOT"})
        assert provider.resolve_field(field_cfg, ctx_root) == "SC_ROOT"

        ctx_params = ResolutionContext(flow_id="f1", phone="123", raw_payload={"parameters": {"school_code": "SC_PARAM"}})
        assert provider.resolve_field(field_cfg, ctx_params) == "SC_PARAM"

    def test_default_data_provider_formats(self):
        provider = DefaultDataProvider()
        field_cfg = FieldConfig("portal_url", FieldSource.DEFAULT, default_value="https://fallback.example.com")

        ctx_root = ResolutionContext(flow_id="f1", phone="123", raw_payload={"portal_url": "https://root.example.com"})
        assert provider.resolve_field(field_cfg, ctx_root) == "https://root.example.com"

        ctx_params = ResolutionContext(flow_id="f1", phone="123", raw_payload={"parameters": {"portal_url": "https://param.example.com"}})
        assert provider.resolve_field(field_cfg, ctx_params) == "https://param.example.com"


class TestBuilderPayloadFormats:
    def test_builder_with_both_payload_formats(self):
        prv = JsonFileConfigProvider()
        reg = FlowRegistry(config_provider=prv)
        builder = ContextBuilder(registry=reg)

        # Passing fields inside parameters dict
        payload_params = {
            "flow_category": "priority",
            "contact": {"phone": "919876543210"},
            "parameters": {
                "state": "Maharashtra",
                "district": "Pune",
                "custom_field": "custom_val"
            }
        }
        res_params = builder.build_context(payload_params)
        assert res_params["state"] == "Maharashtra"
        assert res_params["district"] == "Pune"
        assert res_params["custom_field"] == "custom_val"

        # Passing fields at root level
        payload_root = {
            "flow_category": "priority",
            "phone": "919876543210",
            "state": "Maharashtra",
            "district": "Pune",
            "custom_field": "custom_val"
        }
        res_root = builder.build_context(payload_root)
        assert res_root["state"] == "Maharashtra"
        assert res_root["district"] == "Pune"
        assert res_root["custom_field"] == "custom_val"


class TestAPIPayloadFormats:
    @patch("tap_buddy.dynamic_context.api.frappe.get_single")
    def test_api_handle_parameters_format(self, mock_get_single):
        settings_mock = MagicMock()
        settings_mock.get_password.return_value = "test_secret"
        settings_mock.webhook_secret = "test_secret"
        mock_get_single.return_value = settings_mock

        payload = {
            "parameters": {
                "secret": "test_secret",
                "flow_category": "priority",
                "state": "Delhi",
                "district": "South Delhi"
            }
        }
        mock_req = MagicMock()
        mock_req.get_data = MagicMock(return_value=json.dumps(payload))
        frappe.request = mock_req
        frappe.flags.in_test = True

        res = handle()
        assert res["success"] is True
        assert res["context"]["state"] == "Delhi"
        assert res["context"]["district"] == "South Delhi"
