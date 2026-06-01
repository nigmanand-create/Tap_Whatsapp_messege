import json
import types

import tap_buddy.services.lms_client as lms_client

# ---------------------------------------------------------------------------
# TEST FIXTURE SECURITY NOTICE
# ---------------------------------------------------------------------------
# All credentials in this file are safe, non-functional mock placeholders.
# Do NOT replace them with real API keys, tokens, or secrets.
# ---------------------------------------------------------------------------

_MOCK_LMS_BASE_URL = "https://lms.example-test.invalid"
_MOCK_LMS_API_KEY = "mock-api-user:mock-api-secret-00000"


def _make_settings():
    return types.SimpleNamespace(
        lms_base_url=_MOCK_LMS_BASE_URL,
        lms_api_key=_MOCK_LMS_API_KEY,
    )


def test_get_students_builds_request_params(monkeypatch):
    # Provide fake settings via frappe.get_single
    monkeypatch.setattr("frappe.get_single", lambda name: _make_settings())

    # Patch get_decrypted_password at source (imported inline inside LMSClient.__init__)
    monkeypatch.setattr(
        "frappe.utils.password.get_decrypted_password",
        lambda doctype, name, fieldname, raise_exception=True: _MOCK_LMS_API_KEY,
    )

    # Patch frappe.throw to raise a plain exception instead of touching Frappe flags
    monkeypatch.setattr("frappe.throw", lambda msg: (_ for _ in ()).throw(Exception(msg)))

    # Capture the args passed to session.request (LMSClient uses self.session.request internally)
    captured = {}

    class FakeResp:
        def __init__(self, data):
            self._data = data
            self.text = json.dumps(data)
            self.status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    def fake_request(method, url, headers=None, timeout=None, params=None, **kwargs):
        captured["method"] = method
        captured["url"] = url
        captured["headers"] = headers
        captured["params"] = params
        return FakeResp({"data": [{"name": "S1", "phone": "+911234"}]})

    client = lms_client.LMSClient()
    # Patch the session after construction — session.request is what _request() calls
    client.session.request = fake_request
    result = client.get_students(fields=["name", "phone"], limit_page_length=5)

    assert "data" in result
    assert captured["method"] == "GET"
    assert captured["url"] == f"{_MOCK_LMS_BASE_URL}/api/resource/Student"
    assert "fields" in captured["params"]
    assert json.loads(captured["params"]["fields"]) == ["name", "phone"]
    assert int(captured["params"]["limit_page_length"]) == 5
