import frappe
import pytest
from tap_buddy.services.glific_client import GlificClient, GlificTerminalError

def setup_module(module):
    frappe.init(site="tapbuddy.local")
    frappe.connect()

class MockGlificClient(GlificClient):
    def send_message(self, *args, **kwargs):
        raise GlificTerminalError("24 hrs window closed")
    
    def get_template_by_name(self, template_name):
        # Prevent it from actually hitting Glific API during fallback processing
        # We just want to prove it got to this point
        raise Exception("MOCK_FALLBACK_PROCEEDS")


def test_hsm_fallback_none_blocked():
    """Scenario A: hsm_parameters=None -> fallback blocked, terminal error raised"""
    client = MockGlificClient()
    with pytest.raises(GlificTerminalError) as exc_info:
        client.send_message_with_hsm_fallback(
            phone="919999999999",
            message="Hello None",
            hsm_template_name="hello_none",
            hsm_parameters=None
        )
    assert "24 hrs window closed" in str(exc_info.value)


def test_hsm_fallback_empty_list_proceeds():
    """Scenario B: hsm_parameters=[] -> fallback proceeds"""
    client = MockGlificClient()
    with pytest.raises(Exception) as exc_info:
        client.send_message_with_hsm_fallback(
            phone="919999999999",
            message="Hello Empty",
            hsm_template_name="hello_empty",
            hsm_parameters=[]
        )
    assert "MOCK_FALLBACK_PROCEEDS" in str(exc_info.value)


def test_hsm_fallback_with_vars_proceeds():
    """Scenario C: hsm_parameters=['John'] -> fallback proceeds"""
    client = MockGlificClient()
    with pytest.raises(Exception) as exc_info:
        client.send_message_with_hsm_fallback(
            phone="919999999999",
            message="Hello John",
            hsm_template_name="hello_var",
            hsm_parameters=["John"]
        )
    assert "MOCK_FALLBACK_PROCEEDS" in str(exc_info.value)
