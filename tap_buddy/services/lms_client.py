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
            if resp.status_code == 401:
                frappe.logger("tap_buddy_lms").info("[AUTH] HTTP 401 Unauthorized detected. Attempting auto-rotation.")
                return self._handle_401_and_retry(method, path, **kwargs)
            frappe.log_error(
                title=f"LMS HTTP {resp.status_code} — {method} {path}",
                message=f"{e}\nResponse: {resp.text[:500]}"
            )
            raise LMSAPIError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        except requests.exceptions.RequestException as e:
            frappe.log_error(title=f"LMS Request Error — {method} {path}", message=str(e))
            raise LMSAPIError(str(e))

    def _handle_401_and_retry(self, method: str, path: str, **kwargs):
        from tap_buddy.services.redis_utils import acquire_lock, release_lock
        
        locked = acquire_lock("lms_token_refresh", timeout=15)
        if not locked:
            frappe.logger("tap_buddy_lms").warning("[AUTH] Failed to acquire lock for LMS rotation.")
            raise LMSAPIError("LMS HTTP 401: Token rotation already in progress but lock timed out.")
            
        try:
            # Check if token was rotated by another worker
            settings = frappe.get_single("LMS Integration Settings")
            try:
                from frappe.utils.password import get_decrypted_password
                current_api_key = get_decrypted_password("LMS Integration Settings", "LMS Integration Settings", "lms_api_key", raise_exception=False)
            except Exception:
                current_api_key = None
                
            # If the header token is different from DB token, someone already rotated it!
            db_token = f"token {current_api_key}" if current_api_key else None
            if current_api_key and self.headers.get("Authorization") != db_token:
                frappe.logger("tap_buddy_lms").info("[AUTH] Token already rotated by another worker. Resuming.")
                self.headers["Authorization"] = db_token
            else:
                self._rotate_keys(settings)
        finally:
            release_lock("lms_token_refresh")
                
        # Retry original request
        url = f"{self.base_url}{path}"
        resp = self.session.request(method, url, headers=self.headers, **kwargs)
        resp.raise_for_status()
        return resp.json() if resp.text.strip() else {}

    def _rotate_keys(self, settings):
        try:
            from frappe.utils.password import get_decrypted_password
            username = settings.lms_username
            password = get_decrypted_password("LMS Integration Settings", "LMS Integration Settings", "lms_password", raise_exception=False)
        except Exception:
            username = None
            password = None
            
        if not username or not password:
            frappe.throw("LMS HTTP 401: Cannot rotate keys because lms_username or lms_password is not set in LMS Integration Settings.")
            
        login_session = requests.Session()
        login_url = f"{self.base_url}/api/method/login"
        login_res = login_session.post(login_url, data={"usr": username, "pwd": password}, verify=False)
        
        if login_res.status_code != 200:
            frappe.logger("tap_buddy_lms").error(f"[AUTH] Auto-rotation login failed: {login_res.text[:200]}")
            frappe.throw("LMS HTTP 401: Auto-rotation failed. Invalid lms_username or lms_password.")
            
        # Generate new keys
        keys_url = f"{self.base_url}/api/method/frappe.core.doctype.user.user.generate_keys"
        keys_res = login_session.post(keys_url, data={"user": username}, verify=False)
        if keys_res.status_code != 200:
            frappe.throw(f"LMS HTTP 401: Auto-rotation failed to generate keys: {keys_res.text[:200]}")
            
        # API Secret returns nested under {"message": {"api_secret": "..."}}
        api_secret = keys_res.json().get("message", {}).get("api_secret")
        if not api_secret:
            # Sometime Frappe returns it differently depending on version
            api_secret = keys_res.json().get("api_secret")
            
        # Get api_key
        user_url = f"{self.base_url}/api/resource/User/{username}"
        user_res = login_session.get(user_url, verify=False)
        if user_res.status_code != 200:
            frappe.throw(f"LMS HTTP 401: Auto-rotation failed to get user details: {user_res.text[:200]}")
            
        api_key = user_res.json().get("data", {}).get("api_key")
        
        if not api_key or not api_secret:
            frappe.throw("LMS HTTP 401: Auto-rotation failed to parse new keys.")
            
        new_token = f"{api_key}:{api_secret}"
        
        from frappe.utils.password import set_encrypted_password
        set_encrypted_password("LMS Integration Settings", "LMS Integration Settings", new_token, "lms_api_key")
        frappe.db.commit()
        
        self.headers["Authorization"] = f"token {new_token}"
        frappe.logger("tap_buddy_lms").info("[AUTH] Auto-rotation successful. New LMS API keys generated and saved.")

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
