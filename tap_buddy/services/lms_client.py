import json
import os
import frappe
import requests


class LMSAPIError(Exception):
    pass


class LMSClient:
    """Minimal client for LMS HTTP API used by TAP Buddy polling.

    Expects `LMS Integration Settings` to provide `lms_base_url` and `lms_api_key`.
    The LMS uses an Authorization header of the form: `token <api_key>`.
    """

    def __init__(self):
        # Prefer site settings, fall back to environment variables.
        settings = frappe.get_single("LMS Integration Settings")
        base_url = getattr(settings, "lms_base_url", None) or os.getenv("LMS_BASE_URL")
        api_key = getattr(settings, "lms_api_key", None) or os.getenv("LMS_API_KEY")

        if not base_url or not api_key:
            frappe.throw("LMS base URL and API key must be configured in LMS Integration Settings or provided via environment variables.")

        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"token {self.api_key}",
        }

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            resp = requests.request(method, url, headers=self.headers, timeout=15, **kwargs)
            resp.raise_for_status()
            return resp.json() if resp.text else {}
        except requests.exceptions.RequestException as e:
            frappe.log_error(title=f"LMS API Error - {method} {path}", message=str(e))
            raise LMSAPIError(str(e))

    def get_resource(self, resource: str, fields=None, limit_page_length: int = 20, filters: dict | None = None):
        """Fetch a resource list from the LMS API using Frappe resource endpoint style.

        Example curl from user:
        curl -sS -k "https://lms.evalix.xyz/api/resource/Student?fields=[\"name\",\"name1\",\"phone\",\"glific_id\"]&limit_page_length=20"
        """
        params = {}
        if fields:
            params["fields"] = json.dumps(fields)
        params["limit_page_length"] = int(limit_page_length or 20)
        if filters:
            params["filters"] = json.dumps(filters)

        return self._request("GET", f"/api/resource/{resource}", params=params)


    def get_students(self, fields=None, limit_page_length: int = 20, filters: dict | None = None):
        return self.get_resource("Student", fields=fields or ["name", "name1", "phone", "glific_id"], limit_page_length=limit_page_length, filters=filters)
