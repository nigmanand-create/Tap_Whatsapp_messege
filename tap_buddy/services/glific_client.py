import frappe
import requests

class GlificAPIError(Exception):
    pass

class GlificClient:
    def __init__(self):
        settings = frappe.get_single("TAP Buddy Settings")
        if not settings.glific_url or not settings.glific_token:
            frappe.throw("Glific URL and Token must be configured in TAP Buddy Settings.")
            
        self.base_url = settings.glific_url.rstrip("/")
        # Prefer short-lived access token when available, fallback to primary token
        self.token = getattr(settings, "glific_access_token", None) or settings.glific_token
        self.primary_token = settings.glific_token
        self.refresh_token = getattr(settings, "glific_refresh_token", None)
        self.token_expiry = getattr(settings, "glific_token_expiry", None)

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def ensure_valid_token(self):
        """Placeholder to refresh access token when expired.

        Currently this is a no-op that logs if expiry has passed and a refresh token
        is available. Implement actual refresh flow if Glific exposes a token endpoint.
        """
        if not self.token_expiry or not self.refresh_token:
            return
        try:
            from dateutil.parser import parse as parse_dt
        except Exception:
            return

        try:
            expiry = parse_dt(self.token_expiry)
            import datetime
            if expiry <= datetime.datetime.utcnow():
                frappe.log_error(title="Glific token expired", message="Access token expired and refresh token is present — implement refresh flow")
        except Exception:
            # ignore parse errors
            return

    def _request(self, method, path, **kwargs):
        url = f"{self.base_url}{path}"
        try:
            response = requests.request(method, url, headers=self.headers, timeout=10, **kwargs)
            response.raise_for_status()
            return response.json() if response.text else {}
        except requests.exceptions.RequestException as e:
            frappe.log_error(title=f"Glific API Error - {method} {path}", message=str(e))
            raise GlificAPIError(f"Glific API request failed: {str(e)}")

    def authenticate(self):
        # In a real implementation this might check token validity
        # or do a test request.
        return True

    def send_message(self, phone, message, idempotency_key=None):
        url = f"{self.base_url}/messages"
        payload = {
            "phone": phone,
            "body": message
        }
        headers = dict(self.headers)
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            frappe.log_error(title="Glific API Error - send_message", message=str(e))
            raise GlificAPIError(f"Failed to send message: {str(e)}")

    def get_contact(self, phone):
        url = f"{self.base_url}/contacts"
        params = {"phone": phone}
        
        try:
            response = requests.get(url, params=params, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            frappe.log_error(title="Glific API Error - get_contact", message=str(e))
            raise GlificAPIError(f"Failed to get contact: {str(e)}")

    def create_contact(self, payload):
        return self._request("POST", "/contacts", json=payload)

    def update_contact(self, contact_id, payload):
        return self._request("PUT", f"/contacts/{contact_id}", json=payload)

    def upsert_contact(self, payload):
        phone = payload.get("phone")
        if not phone:
            raise GlificAPIError("Contact payload missing phone")
        existing = self.get_contact(phone)
        contact_id = _extract_contact_id(existing)
        if contact_id:
            return self.update_contact(contact_id, payload)
        return self.create_contact(payload)

    def add_contact_to_group(self, group_id, contact_id):
        payload = {"contact_id": contact_id}
        return self._request("POST", f"/groups/{group_id}/contacts", json=payload)


def _extract_contact_id(response):
    if not response:
        return None
    if isinstance(response, dict):
        if "id" in response:
            return response.get("id")
        if "data" in response and isinstance(response["data"], dict):
            return response["data"].get("id")
        if "contact" in response and isinstance(response["contact"], dict):
            return response["contact"].get("id")
    if isinstance(response, list) and response:
        first = response[0]
        if isinstance(first, dict) and "id" in first:
            return first.get("id")
    return None
