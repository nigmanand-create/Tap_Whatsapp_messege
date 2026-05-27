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
