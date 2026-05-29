import json
import os
import frappe
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class LMSAPIError(Exception):
    pass


class LMSClient:
    """HTTP client for the TAP LMS API (evalix.xyz / Frappe-based).

    Reads credentials from `LMS Integration Settings`.
    API key format: ``api_key:api_secret``  (Frappe token auth).

    Usage::
        client = LMSClient()
        students = client.get_all_students()
    """

    DEFAULT_STUDENT_FIELDS = [
        "name", "name1", "phone", "glific_id",
        "school_id", "grade", "section", "gender", "status"
    ]
    PAGE_SIZE = 100

    def __init__(self):
        settings = frappe.get_single("LMS Integration Settings")
        base_url = getattr(settings, "lms_base_url", None) or os.getenv("LMS_BASE_URL")

        # lms_api_key is a Password field (encrypted at rest) — use get_decrypted_password
        try:
            from frappe.utils.password import get_decrypted_password
            api_key = get_decrypted_password(
                "LMS Integration Settings", "LMS Integration Settings",
                "lms_api_key", raise_exception=False
            )
        except Exception:
            api_key = None
        api_key = api_key or os.getenv("LMS_API_KEY")

        if not base_url or not api_key:
            frappe.throw(
                "LMS base URL and API key must be configured in "
                "LMS Integration Settings or via LMS_BASE_URL / LMS_API_KEY env vars."
            )

        self.base_url = base_url.rstrip("/")
        self.headers  = {
            "Content-Type": "application/json",
            "Accept":       "application/json",
            "Authorization": f"token {api_key}",
        }

        # Session with retry backoff
        self.session = requests.Session()
        retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://",  adapter)

    # ─── Core request ─────────────────────────────────────────────────────

    def _request(self, method: str, path: str, **kwargs):
        url = f"{self.base_url}{path}"
        kwargs.setdefault("timeout", 20)
        kwargs.setdefault("verify",  False)   # evalix.xyz self-signed cert
        try:
            resp = self.session.request(method, url, headers=self.headers, **kwargs)
            resp.raise_for_status()
            return resp.json() if resp.text.strip() else {}
        except requests.exceptions.HTTPError as e:
            frappe.log_error(
                title=f"LMS HTTP {resp.status_code} — {method} {path}",
                message=f"{e}\nResponse: {resp.text[:500]}"
            )
            raise LMSAPIError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        except requests.exceptions.RequestException as e:
            frappe.log_error(title=f"LMS Request Error — {method} {path}", message=str(e))
            raise LMSAPIError(str(e))

    # ─── Generic resource fetch ────────────────────────────────────────────

    def get_resource(self, resource: str, fields=None, limit_page_length: int = 100,
                     filters=None, limit_start: int = 0):
        """Fetch a single page from any LMS doctype resource endpoint."""
        params = {
            "limit_page_length": int(limit_page_length),
            "limit_start": int(limit_start),
        }
        if fields:
            params["fields"] = json.dumps(fields)
        if filters:
            params["filters"] = json.dumps(filters)
        return self._request("GET", f"/api/resource/{resource}", params=params)

    def get_all_resource(self, resource: str, fields=None, filters=None):
        """Auto-paginate through ALL pages of a resource and return combined list."""
        all_records = []
        start = 0
        while True:
            resp = self.get_resource(
                resource,
                fields=fields,
                limit_page_length=self.PAGE_SIZE,
                filters=filters,
                limit_start=start,
            )
            page = resp.get("data", []) if isinstance(resp, dict) else (resp or [])
            if not page:
                break
            all_records.extend(page)
            if len(page) < self.PAGE_SIZE:
                break          # reached last page
            start += self.PAGE_SIZE
        return all_records

    # ─── Typed helpers ────────────────────────────────────────────────────

    def get_students(self, fields=None, limit_page_length: int = 100,
                     filters=None, limit_start: int = 0):
        """Fetch a single page of students."""
        return self.get_resource(
            "Student",
            fields=fields or self.DEFAULT_STUDENT_FIELDS,
            limit_page_length=limit_page_length,
            filters=filters,
            limit_start=limit_start,
        )

    def get_all_students(self, fields=None, filters=None):
        """Fetch ALL students with auto-pagination (handles large datasets)."""
        return self.get_all_resource(
            "Student",
            fields=fields or self.DEFAULT_STUDENT_FIELDS,
            filters=filters,
        )

    def get_school(self, school_id: str):
        """Fetch a single LMS School by ID."""
        return self._request("GET", f"/api/resource/School/{school_id}")

    def get_all_schools(self, fields=None):
        """Fetch all LMS Schools (for school mapping)."""
        return self.get_all_resource(
            "School",
            fields=fields or ["name", "school_name"],
        )
