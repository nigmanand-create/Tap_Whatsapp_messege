import frappe
import pytest
from unittest.mock import patch, MagicMock
from frappe.utils.password import get_decrypted_password, set_encrypted_password
from tap_buddy.services.lms_client import LMSClient

def setup_module(module):
    frappe.init(site="tapbuddy.local")
    frappe.connect()

def setup_function(function):
    # Ensure baseline settings exist
    if not frappe.db.exists("LMS Integration Settings", "LMS Integration Settings"):
        frappe.get_doc({
            "doctype": "LMS Integration Settings",
        }).insert(ignore_permissions=True)
    
    settings = frappe.get_single("LMS Integration Settings")
    settings.lms_base_url = "https://mock-lms.local"
    settings.lms_username = "mock-admin"
    settings.lms_api_key = "*****"  # Dummy to pass validation, actual key is in __Auth
    settings.save(ignore_permissions=True)
    
    frappe.cache().delete_keys("LMS Integration Settings")
    frappe.clear_cache(doctype="LMS Integration Settings")
    set_encrypted_password("LMS Integration Settings", "LMS Integration Settings", "old_key:old_secret", "lms_api_key")
    set_encrypted_password("LMS Integration Settings", "LMS Integration Settings", "mock-pass", "lms_password")
    frappe.db.commit()


def test_scenario_a_persistence():
    """Scenario A: set_encrypted_password persists token, get_decrypted_password reloads new token"""
    new_token = "token_a:secret_a"
    set_encrypted_password("LMS Integration Settings", "LMS Integration Settings", new_token, "lms_api_key")
    frappe.db.commit()
    
    reloaded_token = get_decrypted_password("LMS Integration Settings", "LMS Integration Settings", "lms_api_key")
    assert reloaded_token == new_token, f"Expected {new_token}, got {reloaded_token}"


@patch("tap_buddy.services.lms_client.requests.Session")
def test_scenario_b_and_c_simulated_rotation(mock_session_class):
    """Scenario B: simulated 401, _rotate_keys() generates new token, subsequent LMSClient instance loads the rotated token
       Scenario C: old token is no longer returned after rotation"""
    
    # Setup mocks
    mock_session = MagicMock()
    mock_session_class.return_value = mock_session
    
    # We need to simulate the sequence of responses for client._request and _rotate_keys
    
    # 1. Initial request -> 401
    # 2. _rotate_keys -> login -> 200
    # 3. _rotate_keys -> generate_keys -> 200 (api_secret)
    # 4. _rotate_keys -> get user -> 200 (api_key)
    # 5. Retry request -> 200
    
    resp_401 = MagicMock()
    resp_401.status_code = 401
    import requests
    resp_401.raise_for_status.side_effect = requests.exceptions.HTTPError("401", response=resp_401)
    
    resp_login = MagicMock()
    resp_login.status_code = 200
    resp_login.json.return_value = {"message": "Logged In"}
    
    resp_keys = MagicMock()
    resp_keys.status_code = 200
    resp_keys.json.return_value = {"message": {"api_secret": "rot_secret"}}
    
    resp_user = MagicMock()
    resp_user.status_code = 200
    resp_user.json.return_value = {"data": {"api_key": "rot_key"}}
    
    resp_success = MagicMock()
    resp_success.status_code = 200
    resp_success.json.return_value = {"data": [{"name": "MockStudent"}]}
    resp_success.text = "has body"
    
    # request() is called for the initial fetch, and retry fetch
    # post() is called for login and generate_keys
    # get() is called for get user details
    
    mock_session.request.side_effect = [resp_401, resp_success]
    mock_session.post.side_effect = [resp_login, resp_keys]
    mock_session.get.side_effect = [resp_user]
    
    client = LMSClient()
    
    # Replace the actual sessions created inside _rotate_keys with our mock
    # Wait, LMSClient uses self.session for request, and a new Session() for login!
    # Our mock_session_class will intercept all Session() calls.
    
    # Trigger the flow
    result = client.get_resource("Student")
    
    # Verify the retry worked
    assert result.get("data")[0]["name"] == "MockStudent"
        
    # Scenario B: Verify a completely new instance loads the rotated token
    new_client = LMSClient()
    assert new_client.headers["Authorization"] == "token rot_key:rot_secret", \
        f"New client loaded wrong token: {new_client.headers['Authorization']}"
        
    # Scenario C: Old token is no longer returned
    db_token = get_decrypted_password("LMS Integration Settings", "LMS Integration Settings", "lms_api_key")
    assert db_token == "rot_key:rot_secret", f"DB token was not updated correctly, got {db_token}"
    assert db_token != "old_key:old_secret", "Old token is still returned!"
