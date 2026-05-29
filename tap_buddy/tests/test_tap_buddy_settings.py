import pytest
import frappe
from tap_buddy.tap_buddy.doctype.tap_buddy_settings.tap_buddy_settings import TAPBuddySettings

class TestTAPBuddySettingsValidation:
    @pytest.fixture(autouse=True)
    def patch_init(self, monkeypatch):
        monkeypatch.setattr(TAPBuddySettings, "__init__", lambda self, *args, **kwargs: None)
        monkeypatch.setattr("tap_buddy.tap_buddy.doctype.tap_buddy_settings.tap_buddy_settings.frappe.throw", lambda msg: (_ for _ in ()).throw(frappe.ValidationError(msg)))
        
    def test_missing_refresh_token_fails(self, monkeypatch):
        doc = TAPBuddySettings()
        
        # Mock get_password since we don't have a real DB doc context
        def mock_get_password(fieldname):
            if fieldname == "glific_access_token":
                return "has_access_token"
            if fieldname == "glific_refresh_token":
                return None
            return None
            
        monkeypatch.setattr(doc, "get_password", mock_get_password)
        
        with pytest.raises(frappe.ValidationError, match="A Refresh Token must be provided"):
            doc.validate_glific_tokens()

    def test_both_tokens_succeeds(self, monkeypatch):
        doc = TAPBuddySettings()
        
        def mock_get_password(fieldname):
            if fieldname == "glific_access_token":
                return "has_access_token"
            if fieldname == "glific_refresh_token":
                return "has_refresh_token"
            return None
            
        monkeypatch.setattr(doc, "get_password", mock_get_password)
        
        # Should not raise
        doc.validate_glific_tokens()

    def test_no_tokens_succeeds(self, monkeypatch):
        doc = TAPBuddySettings()
        
        def mock_get_password(fieldname):
            return None
            
        monkeypatch.setattr(doc, "get_password", mock_get_password)
        
        # Should not raise
        doc.validate_glific_tokens()
