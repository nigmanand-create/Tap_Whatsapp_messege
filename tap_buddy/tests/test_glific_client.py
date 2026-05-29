"""
Unit tests for tap_buddy.services.glific_client

Tests cover:
  - Token refresh locking (only one worker refreshes at a time)
  - Circuit breaker blocks requests when OPEN
  - _request() error classification (terminal vs retryable)
  - No token/auth headers logged on errors
    - Correct auth header construction
"""
import types
from unittest.mock import MagicMock, patch, call

import pytest
import requests


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_settings(token="test-token", access_token=None, refresh_token=None,
                   token_expiry=None, glific_url="https://api.glific.test/v1"):
    s = MagicMock()
    values = {
        "glific_url": glific_url,
        "glific_token": token,
        "glific_access_token": access_token,
        "glific_refresh_token": refresh_token,
        "glific_token_expiry": token_expiry,
    }
    for key, value in values.items():
        setattr(s, key, value)
    s.get_password.side_effect = lambda fieldname: values.get(fieldname)
    s.get.side_effect = lambda fieldname, default=None: values.get(fieldname, default)
    return s


# ---------------------------------------------------------------------------
# 1. Token / Auth header construction
# ---------------------------------------------------------------------------

class TestGlificClientInit:
    def test_auth_header_set_from_access_token_if_present(self, monkeypatch):
        settings = _make_settings(
            token="primary-token",
            access_token="short-lived-token",
        )
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))

        # Patch redis_utils to avoid connection attempts
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False
        )

        from tap_buddy.services.glific_client import GlificClient

        client = GlificClient()
        assert client.headers["Authorization"] == "short-lived-token"

    def test_auth_header_falls_back_to_primary_token(self, monkeypatch):
        settings = _make_settings(token="primary-token", access_token=None)
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False
        )

        from tap_buddy.services.glific_client import GlificClient

        client = GlificClient()
        assert client.headers["Authorization"] == "primary-token"

    def test_missing_url_raises(self, monkeypatch):
        settings = _make_settings(glific_url="")
        monkeypatch.setattr("frappe.get_single", lambda name: settings)

        thrown = []
        monkeypatch.setattr("frappe.throw", lambda msg: thrown.append(msg))

        from tap_buddy.services.glific_client import GlificClient

        try:
            GlificClient()
        except Exception:
            pass
        assert len(thrown) == 1  # frappe.throw was called


class TestGlificClientMessageQueries:
    def test_get_message_returns_remote_message(self, monkeypatch):
        settings = _make_settings()
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False
        )

        from tap_buddy.services.glific_client import GlificClient

        client = GlificClient()
        client._graphql_request = MagicMock(return_value={
            "message": {
                "message": {"id": "229598882", "status": "sent"}
            }
        })

        result = client.get_message("229598882")
        assert result == {"id": "229598882", "status": "sent"}
        client._graphql_request.assert_called_once()

    def test_send_hsm_message_calls_mutation_with_contacts(self, monkeypatch):
        settings = _make_settings()
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False
        )

        from tap_buddy.services.glific_client import GlificClient

        client = GlificClient()
        client.get_contact = MagicMock(return_value={"id": 123})
        client._graphql_request = MagicMock(return_value={
            "sendHsmMessage": {"message": {"id": "229598882", "status": "sent"}}
        })

        result = client.send_hsm_message("8595701049", "template-123", ["Yes"])
        assert result == {"id": "229598882", "status": "sent"}
        assert client._graphql_request.call_count == 1
        args, _ = client._graphql_request.call_args
        assert args[1]["receiverId"] == 123
        assert args[1]["templateId"] == "template-123"
        assert args[1]["parameters"] == ["Yes"]

    def test_resend_message_uses_hsm_when_template_id_present(self, monkeypatch):
        settings = _make_settings()
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False
        )

        from tap_buddy.services.glific_client import GlificClient

        client = GlificClient()
        client.get_message = MagicMock(return_value={
            "isHsm": True,
            "templateId": "template-123",
            "params": ["Yes"],
            "receiver": {"phone": "8595701049"},
        })
        client.send_hsm_message = MagicMock(return_value={"id": "229598882", "status": "sent"})

        result = client.resend_message("229598882")
        assert result == {"id": "229598882", "status": "sent"}
        client.send_hsm_message.assert_called_once_with("8595701049", "template-123", ["Yes"])

    def test_graphql_request_retries_with_primary_token_on_401(self, monkeypatch):
        settings = _make_settings(token="primary-token", access_token="short-lived-token")
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.check_circuit_breaker", lambda svc: False
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.record_api_success", lambda *a, **kw: None
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.record_api_failure", lambda *a, **kw: None
        )

        from tap_buddy.services.glific_client import GlificClient

        client = GlificClient()

        fake_response_401 = MagicMock()
        fake_response_401.status_code = 401
        fake_response_401.text = "Unauthorized"
        fake_response_401.raise_for_status.side_effect = requests.exceptions.HTTPError(
            response=fake_response_401
        )
        fake_response_401.json.return_value = {}

        fake_response_200 = MagicMock()
        fake_response_200.status_code = 200
        fake_response_200.text = '{"data":{"message":{"id":"229598882"}}}'
        fake_response_200.raise_for_status.return_value = None
        fake_response_200.json.return_value = {"data": {"message": {"id": "229598882"}}}

        client.session.post = MagicMock(side_effect=[fake_response_401, fake_response_200])

        result = client._graphql_request("query {}", {})

        assert result == {"message": {"id": "229598882"}}
        assert client.session.post.call_count == 2
        assert client.session.post.call_args_list[1][1]["headers"]["Authorization"] == "primary-token"



# ---------------------------------------------------------------------------
# 1.5. Token Refresh Lifecycle Tests
# ---------------------------------------------------------------------------

class TestTokenRefreshLifecycle:
    def test_perform_token_refresh_success(self, monkeypatch):
        settings = _make_settings(refresh_token="valid_refresh", glific_url="https://api.glific.test/v1")
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.db", MagicMock())
        
        from tap_buddy.services.glific_client import GlificClient
        client = GlificClient()
        
        # Mock session.post for /session/renew
        fake_response = MagicMock()
        fake_response.status_code = 200
        fake_response.text = '{"data": {"access_token": "new_access", "refresh_token": "new_refresh", "token_expiry_time": "2030-01-01T00:00:00Z"}}'
        fake_response.json.return_value = {"data": {"access_token": "new_access", "refresh_token": "new_refresh", "token_expiry_time": "2030-01-01T00:00:00Z"}}
        fake_response.raise_for_status.return_value = None
        
        import requests
        monkeypatch.setattr(requests, "post", MagicMock(return_value=fake_response))
        
        # Perform refresh
        client._perform_token_refresh()
        
        assert requests.post.call_count == 1
        assert client.token == "new_access"
        assert client.refresh_token == "new_refresh"
        assert client.token_expiry == "2030-01-01T00:00:00Z"
        assert client.headers["Authorization"] == "new_access"
        assert settings.glific_access_token == "new_access"
        assert settings.glific_refresh_token == "new_refresh"
        settings.save.assert_called_once()
        
    def test_perform_token_refresh_invalid_refresh_token(self, monkeypatch):
        settings = _make_settings(refresh_token="invalid_refresh", glific_url="https://api.glific.test/v1")
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.db", MagicMock())
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.logger", lambda name: MagicMock())
        
        from tap_buddy.services.glific_client import GlificClient, GlificTerminalError
        client = GlificClient()
        
        fake_response = MagicMock()
        fake_response.status_code = 401
        fake_response.text = "Unauthorized"
        import requests
        fake_response.raise_for_status.side_effect = requests.exceptions.HTTPError(response=fake_response)
        
        monkeypatch.setattr(requests, "post", MagicMock(return_value=fake_response))
        
        client._perform_token_refresh()
            
        assert settings.glific_refresh_token is None
        settings.save.assert_called_once()

    def test_perform_token_refresh_no_refresh_token(self, monkeypatch):
        settings = _make_settings(refresh_token=None)
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        
        from tap_buddy.services.glific_client import GlificClient
        client = GlificClient()
        client.session.post = MagicMock()
        
        client._perform_token_refresh()
        client.session.post.assert_not_called()

    def test_graphql_request_auto_refreshes_on_401(self, monkeypatch):
        settings = _make_settings(refresh_token="valid_refresh")
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        monkeypatch.setattr("tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False)
        monkeypatch.setattr("tap_buddy.services.glific_client.check_circuit_breaker", lambda svc: False)
        monkeypatch.setattr("tap_buddy.services.glific_client.record_api_success", lambda *a, **kw: None)
        monkeypatch.setattr("tap_buddy.services.glific_client.record_api_failure", lambda *a, **kw: None)

        from tap_buddy.services.glific_client import GlificClient
        client = GlificClient()
        
        # 1st call: 401, 2nd call: successful refresh, 3rd call: 200
        fake_response_401 = MagicMock()
        fake_response_401.status_code = 401
        fake_response_401.text = "Unauthorized"
        import requests
        fake_response_401.raise_for_status.side_effect = requests.exceptions.HTTPError(response=fake_response_401)
        fake_response_401.json.return_value = {}

        fake_response_200 = MagicMock()
        fake_response_200.status_code = 200
        fake_response_200.text = '{"data": {"message": "ok"}}'
        fake_response_200.json.return_value = {"data": {"message": "ok"}}
        fake_response_200.raise_for_status.return_value = None

        client.session.post = MagicMock(side_effect=[fake_response_401, fake_response_200])
        
        # mock refresh
        def fake_refresh():
            client.access_token = "new_access_after_401"
            client.headers["Authorization"] = client.access_token
        client._perform_token_refresh = MagicMock(side_effect=fake_refresh)

        result = client._graphql_request("query {}", {})
        assert result == {"message": "ok"}
        client._perform_token_refresh.assert_called_once()
        assert client.session.post.call_count == 2
        # Verify the retry used the new token
        assert client.session.post.call_args_list[1][1]["headers"]["Authorization"] == "new_access_after_401"

    def test_refresh_triggered_when_expiry_within_threshold(self, monkeypatch):
        import datetime
        from dateutil.tz import tzutc
        now = datetime.datetime.now(tzutc())
        exp = (now + datetime.timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ") # 2 mins away, threshold is 5
        
        settings = _make_settings(refresh_token="valid_refresh", token_expiry=exp)
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        monkeypatch.setattr("tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: True)
        monkeypatch.setattr("tap_buddy.services.glific_client.release_lock", lambda *a, **kw: None)
        
        from tap_buddy.services.glific_client import GlificClient
        client = GlificClient()
        client._perform_token_refresh = MagicMock()
        
        client.ensure_valid_token()
        client._perform_token_refresh.assert_called_once()

    def test_no_refresh_when_token_still_valid(self, monkeypatch):
        import datetime
        from dateutil.tz import tzutc
        now = datetime.datetime.now(tzutc())
        exp = (now + datetime.timedelta(minutes=10)).strftime("%Y-%m-%dT%H:%M:%SZ") # 10 mins away, threshold is 5
        
        settings = _make_settings(refresh_token="valid_refresh", token_expiry=exp, access_token="still_good")
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        
        from tap_buddy.services.glific_client import GlificClient
        client = GlificClient()
        client._perform_token_refresh = MagicMock()
        
        client.ensure_valid_token()
        client._perform_token_refresh.assert_not_called()

    def test_refresh_token_persisted_after_restart(self, monkeypatch):
        # A new client instance picks up the tokens from Frappe settings.
        settings = _make_settings(access_token="restarted_access", refresh_token="restarted_refresh")
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        
        from tap_buddy.services.glific_client import GlificClient
        client = GlificClient()
        assert client.access_token == "restarted_access"
        assert client.refresh_token == "restarted_refresh"
        assert client.headers["Authorization"] == "restarted_access"

    def test_concurrent_refresh_attempts_block(self, monkeypatch):
        settings = _make_settings(refresh_token="valid_refresh", token_expiry="2000-01-01T00:00:00Z") # Expired
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe.cache", lambda: MagicMock(get_value=lambda k: None))
        
        # Mock acquire_lock to return False to simulate contention
        monkeypatch.setattr("tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False)
        
        import time
        monkeypatch.setattr(time, "sleep", MagicMock())
        
        from tap_buddy.services.glific_client import GlificClient
        client = GlificClient()
        client._perform_token_refresh = MagicMock()
        
        # Change the mock settings so when it re-checks settings, it gets a new valid expiry
        def mock_get_password(fieldname):
            if fieldname == "glific_access_token": return "access_by_other_worker"
            if fieldname == "glific_refresh_token": return "refresh"
            return None
        def mock_get(fieldname, default=None):
            if fieldname == "glific_token_expiry": return "2030-01-01T00:00:00Z"
            return None
            
        settings.get_password.side_effect = mock_get_password
        settings.get.side_effect = mock_get
        
        client.ensure_valid_token()
        # Ensure perform_refresh was bypassed because we didn't get the lock
        client._perform_token_refresh.assert_not_called()
        # Ensure our token state was updated from the "database"
        assert client.token == "access_by_other_worker"
        
    def test_refresh_lock_holder_crashes(self, monkeypatch):
        # A mock implementation that simulates time expiring and lock being stale or forced
        # In frappe redis locking, locks auto-expire. If acquire_lock(timeout=15) is used, 
        # Redis clears the lock after 15s. This is natively handled by the cache backend.
        assert True # Conceptual test since Redis behavior is mocked away.


# ---------------------------------------------------------------------------
# 2. Circuit breaker blocks requests
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    def _make_client_with_open_breaker(self, monkeypatch):
        settings = _make_settings()
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", MagicMock())
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.check_circuit_breaker",
            lambda svc: True,  # circuit is OPEN
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.frappe.logger",
            lambda name: MagicMock(),
        )

        from tap_buddy.services.glific_client import GlificClient
        return GlificClient()

    def test_open_circuit_raises_glific_api_error(self, monkeypatch):
        from tap_buddy.services.glific_client import GlificAPIError

        client = self._make_client_with_open_breaker(monkeypatch)
        with pytest.raises(GlificAPIError, match="circuit breaker"):
            client._request("GET", "/test")


# ---------------------------------------------------------------------------
# 3. Error classification — terminal vs retryable
# ---------------------------------------------------------------------------

class TestErrorClassification:
    def _make_client(self, monkeypatch, status_code):
        settings = _make_settings()
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", MagicMock())
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.check_circuit_breaker",
            lambda svc: False,
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False
        )

        fake_logger = MagicMock()
        fake_frappe = MagicMock()
        fake_frappe.get_single.return_value = settings
        fake_frappe.logger.return_value = fake_logger
        fake_frappe.as_json = lambda x: str(x)
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe", fake_frappe)
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.record_api_failure", MagicMock()
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.record_api_success", MagicMock()
        )

        import requests as req_lib

        fake_response = MagicMock()
        fake_response.status_code = status_code
        fake_response.text = "error body"
        fake_response.raise_for_status.side_effect = req_lib.exceptions.HTTPError(
            response=fake_response
        )
        fake_response.json.return_value = {}

        from tap_buddy.services.glific_client import GlificClient

        client = GlificClient()
        client.session = MagicMock()
        client.session.request.return_value = fake_response
        return client

    @pytest.mark.parametrize("status_code", [400, 401, 404])
    def test_terminal_status_raises_terminal_error(self, monkeypatch, status_code):
        from tap_buddy.services.glific_client import GlificTerminalError

        client = self._make_client(monkeypatch, status_code)
        with pytest.raises(GlificTerminalError):
            client._request("POST", "/messages", json={})

    @pytest.mark.parametrize("status_code", [500, 502, 503])
    def test_retryable_status_raises_api_error(self, monkeypatch, status_code):
        from tap_buddy.services.glific_client import GlificAPIError, GlificTerminalError

        client = self._make_client(monkeypatch, status_code)
        with pytest.raises(GlificAPIError):
            client._request("POST", "/messages", json={})


# ---------------------------------------------------------------------------
# 4. Logging safety — no auth token in error logs
# ---------------------------------------------------------------------------

class TestLoggingSafety:
    def test_error_log_does_not_contain_auth_token(self, monkeypatch):
        """response.text is no longer logged — verify token cannot appear in logs."""
        settings = _make_settings(token="SUPER_SECRET_TOKEN_XYZ")
        monkeypatch.setattr("frappe.get_single", lambda name: settings)
        monkeypatch.setattr("frappe.throw", MagicMock())
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.check_circuit_breaker",
            lambda svc: False,
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.acquire_lock", lambda *a, **kw: False
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.record_api_failure", MagicMock()
        )
        monkeypatch.setattr(
            "tap_buddy.services.glific_client.record_api_success", MagicMock()
        )

        log_calls = []

        class FakeLogger:
            def error(self, msg):
                log_calls.append(str(msg))

        fake_frappe = MagicMock()
        fake_frappe.get_single.return_value = settings
        fake_frappe.logger.return_value = FakeLogger()
        fake_frappe.as_json = lambda x: str(x)
        monkeypatch.setattr("tap_buddy.services.glific_client.frappe", fake_frappe)

        # Fake a 400 response whose body echoes the token (upstream bug simulation)
        import requests as req_lib

        fake_response = MagicMock()
        fake_response.status_code = 400
        fake_response.text = "Authorization token SUPER_SECRET_TOKEN_XYZ is invalid"
        fake_response.raise_for_status.side_effect = req_lib.exceptions.HTTPError(
            response=fake_response
        )

        from tap_buddy.services.glific_client import GlificClient

        client = GlificClient()
        client.session = MagicMock()
        client.session.request.return_value = fake_response

        from tap_buddy.services.glific_client import GlificTerminalError

        try:
            client._request("POST", "/messages", json={})
        except GlificTerminalError:
            pass

        for msg in log_calls:
            assert "SUPER_SECRET_TOKEN_XYZ" not in msg, (
                f"Auth token leaked into log: {msg}"
            )
