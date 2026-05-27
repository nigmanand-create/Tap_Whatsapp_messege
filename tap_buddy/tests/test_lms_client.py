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

    # Capture the args passed to requests.request
    captured = {}

    class FakeResp:
        def __init__(self, data):
            self._data = data
            self.text = json.dumps(data)

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

    monkeypatch.setattr("tap_buddy.services.lms_client.requests.request", fake_request)

    client = lms_client.LMSClient()
    result = client.get_students(fields=["name", "phone"], limit_page_length=5)

    assert "data" in result
    assert captured["method"] == "GET"
    assert captured["url"] == f"{_MOCK_LMS_BASE_URL}/api/resource/Student"
    assert "fields" in captured["params"]
    assert json.loads(captured["params"]["fields"]) == ["name", "phone"]
    assert int(captured["params"]["limit_page_length"]) == 5
