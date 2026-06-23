import frappe
import json
import logging
from datetime import datetime, timezone
import requests  # type: ignore[import-untyped]
from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]
from urllib3.util.retry import Retry
import time

from tap_buddy.services.redis_utils import acquire_lock, release_lock, check_circuit_breaker, record_api_failure, record_api_success

class GlificTerminalError(Exception):
    """Raised for non-retryable errors like 400 or 404"""
    pass

class GlificAPIError(Exception):
    """Raised for transient/retryable API errors"""
    pass


def get_safe_password(settings, fieldname):
    val = settings.get(fieldname)
    if not val:
        return None
    
    try:
        passwd = settings.get_password(fieldname)
        if isinstance(passwd, str) and passwd and "***" not in passwd:
            return passwd
    except Exception:
        pass
    # fallback to get which might be set temporarily in memory or something
    val = settings.get(fieldname)
    if isinstance(val, str) and val and "***" not in val:
        return val
    return None


def normalize_phone(phone):
    phone = str(phone).replace("+", "").strip()

    if phone.startswith("91"):
        return phone

    if len(phone) == 10:
        return "91" + phone

    return phone
    

def _derive_graphql_url(base_url):
    if base_url.endswith("/api"):
        return base_url
    if "/api/v1" in base_url:
        return f"{base_url.rsplit('/api/v1', 1)[0]}/api"
    return f"{base_url.rstrip('/')}/api"


def _derive_rest_base_url(base_url):
    if "/api/v1" in base_url:
        return f"{base_url.rsplit('/api/v1', 1)[0]}/api/v1"
    if base_url.endswith("/api"):
        return f"{base_url[:-4]}/api/v1"
    return f"{base_url.rstrip('/')}/api/v1"


def _serialize_graphql_errors(errors):
    if isinstance(errors, list):
        messages = [item.get("message") for item in errors if isinstance(item, dict) and item.get("message")]
        if messages:
            return "; ".join(messages)
    if isinstance(errors, dict):
        message = errors.get("message")
        if message:
            return message
    return json.dumps(errors)


def _coerce_glific_fields(fields):
    if not fields:
        return None
    if isinstance(fields, str):
        return fields
    return json.dumps(fields)


def _coerce_glific_id(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return value

def normalize_phone(phone):
    phone = str(phone).replace("+", "").replace(" ", "").replace("-", "").strip()

    if phone.startswith("91"):
        return phone

    if len(phone) == 10:
        return "91" + phone

    return phone
    
class GlificClient:

    def __init__(self):
        settings = frappe.get_single("TAP Buddy Settings")
        
        has_token = get_safe_password(settings, "glific_access_token") or get_safe_password(settings, "glific_token")
        if not settings.glific_url or not has_token:
            frappe.throw("Glific URL and Token must be configured in TAP Buddy Settings.")
            
        self.base_url = settings.glific_url.rstrip("/")
        self.rest_base_url = _derive_rest_base_url(self.base_url)
        self.graphql_url = _derive_graphql_url(self.base_url)
        self.token = get_safe_password(settings, "glific_access_token") or get_safe_password(settings, "glific_token")
        self.primary_token = get_safe_password(settings, "glific_token")
        self.token_expiry = getattr(settings, "glific_token_expiry", None)
        self.base_url = settings.glific_url or "https://api.tap.glific.com/api/v1"
        self.access_token = get_safe_password(settings, "glific_access_token")
        self.refresh_token = get_safe_password(settings, "glific_refresh_token")
        
        # [MOCK INJECTION FOR CYPRESS E2E]
        is_explicit_mock = bool(frappe.cache().get_value("mock_glific"))
        if is_explicit_mock or (self.token and self.token == "*" * 100) or (self.primary_token and self.primary_token == "*" * 100):
            frappe.logger("tap_buddy_glific").info("[MOCK] Glific API mock enabled for E2E tests.")
            self._is_mock = True
        else:
            self._is_mock = False

        self.session = requests.Session()
        # Retry matrix: Exponential backoff for 429, 502, 503, 504
        retry_strategy = Retry(
            total=3,
            status_forcelist=[429, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST", "PUT", "DELETE"],
            backoff_factor=1,
            respect_retry_after_header=True
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

        self.headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json"
        }


    def ensure_valid_token(self):
        if not self.should_refresh_token():
            return

        if not self.refresh_token:
            return

        # Token is missing, expired, expiring soon, or token_expiry is unavailable.
        if acquire_lock("glific_token_refresh", timeout=15):
            try:
                self._perform_token_refresh()
            finally:
                release_lock("glific_token_refresh")
        else:
            # Another worker is refreshing. Sleep briefly and re-fetch settings.
            time.sleep(2)
            settings = frappe.get_single("TAP Buddy Settings")
            self.token = get_safe_password(settings, "glific_access_token") or get_safe_password(settings, "glific_token")
            self.refresh_token = get_safe_password(settings, "glific_refresh_token")
            self.token_expiry = getattr(settings, "glific_token_expiry", None)
            if self.token:
                self.headers["Authorization"] = self.token
            else:
                self.headers.pop("Authorization", None)

    def should_refresh_token(self):
        if not self.refresh_token:
            return False

        if not self.token:
            return True

        if not self.token_expiry:
            return True

        try:
            from dateutil.parser import parse as parse_dt
            import datetime
            expiry = parse_dt(self.token_expiry)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=datetime.timezone.utc)
            now = datetime.datetime.now(datetime.timezone.utc)
            if expiry <= now + datetime.timedelta(minutes=5):
                return True
            return False
        except Exception as exc:
            frappe.logger("tap_buddy_glific").warning(f"Token expiry parse error, forcing refresh: {repr(exc)}")
            return True



    def _perform_token_refresh(self):
        url = f"{self.rest_base_url}/session/renew"
        headers = {
            "Authorization": self.refresh_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        response = None
        try:
            self._log_auth_event("Refresh Started", "Attempting to refresh token via API.", "Info")
            response = requests.post(url, headers=headers, json={}, timeout=10)
            response.raise_for_status()
            response_data = response.json() or {}
            data = response_data.get("data", response_data)
            
            # Extract new token fields
            new_access_token = data.get("access_token")
            new_refresh_token = data.get("renewal_token") or data.get("refresh_token")
            new_expiry = data.get("token_expiry_time") or data.get("expires_at")
            
            if new_access_token:
                settings = frappe.get_single("TAP Buddy Settings")
                settings.glific_access_token = new_access_token
                if new_refresh_token:
                    settings.glific_refresh_token = new_refresh_token
                settings.glific_token_expiry = new_expiry
                settings.save(ignore_permissions=True)
                frappe.db.commit()
                self.token = new_access_token
                self.refresh_token = new_refresh_token or self.refresh_token
                self.token_expiry = new_expiry
                self.headers["Authorization"] = self.token
                self._log_auth_event("Refresh Succeeded", f"Refreshed token successfully. New expiry: {new_expiry}", "Info")
                frappe.logger("tap_buddy_glific").info("Glific token refresh succeeded.")
        except requests.exceptions.HTTPError as e:
            if getattr(response, 'status_code', None) == 401:
                frappe.logger("tap_buddy_glific").error("Token refresh returned 401; clearing invalid refresh token.")
                self.refresh_token = None
                if self.token:
                    self.headers["Authorization"] = self.token
                try:
                    settings = frappe.get_single("TAP Buddy Settings")
                    settings.glific_refresh_token = None
                    settings.save(ignore_permissions=True)
                    frappe.db.commit()
                except Exception as save_exc:
                    frappe.logger("tap_buddy_glific").error(f"Failed to clear refresh token from settings: {repr(save_exc)}")
            
            self._log_auth_event("Refresh Failed", f"Token refresh failed (HTTP {getattr(response, 'status_code', 'unknown')}): {str(e)}", "Error")
            frappe.logger("tap_buddy_glific").error(f"Token refresh failed: {str(e)}")
        except requests.exceptions.RequestException as e:
            self._log_auth_event("Refresh Failed", f"Token refresh request failed: {str(e)}", "Error")
            frappe.logger("tap_buddy_glific").error(f"Token refresh request failed: {str(e)}")
            # Do not throw yet; let the actual API call attempt with the old token
            # and fail naturally if it truly is expired.

    def _log_auth_event(self, event, message, severity):
        try:
            countdown = 0
            if self.token_expiry:
                try:
                    expiry_dt = parser.parse(self.token_expiry)
                    now = datetime.now(expiry_dt.tzinfo or timezone.utc)
                    countdown = int((expiry_dt - now).total_seconds() / 60)
                except Exception:
                    pass
            doc = frappe.get_doc({
                "doctype": "Glific Auth Log",
                "event": event,
                "message": str(message)[:1000],
                "severity": severity,
                "expiry_countdown": countdown,
                "timestamp": frappe.utils.now_datetime()
            })
            doc.insert(ignore_permissions=True)
            frappe.db.commit()
        except Exception as e:
            frappe.logger("tap_buddy_glific").warning(f"Failed to log auth event: {e}")

    def _graphql_request(self, query, variables=None):
        if check_circuit_breaker("glific"):
            frappe.logger("tap_buddy_glific").error("Circuit breaker is OPEN. Dropping request.")
            raise GlificAPIError("Glific circuit breaker is open. Temporarily unavailable.")

        if getattr(self, "_is_mock", False):
            if "createAndSendMessage" in query:
                return {"createAndSendMessage": {"message": {"id": "mock_123", "status": "sent"}}}
            if "sendHsmMessage" in query:
                return {"sendHsmMessage": {"message": {"id": "mock_msg_123", "bspStatus": "sent", "bspMessageId": "mock_bsp_id", "insertedAt": "2026-05-01T00:00:00"}}}
            if "sessionTemplates" in query:
                shortcode = variables.get("filter", {}).get("term", "mock") if variables else "mock"
                return {"sessionTemplates": [{"id": "mock_tmpl_123", "shortcode": shortcode, "status": "APPROVED", "numberParameters": 4}]}
            if "optinContact" in query:
                return {"optinContact": {"contact": {"id": "mock_contact_123", "bspStatus": "OPTED_IN"}}}
            if "contactByPhone" in query or "contact(" in query:
                return {"contactByPhone": {"contact": {"id": "mock_contact_123"}}, "contact": {"id": "mock_contact_123"}}
            if "createContact" in query:
                return {"createContact": {"contact": {"id": "mock_contact_123"}}}
            if "createSessionTemplate" in query:
                return {"createSessionTemplate": {"template": {"id": "mock_tmpl_123", "shortcode": variables.get("input", {}).get("shortcode", "mock"), "status": "PENDING"}}}
            if "languages(" in query:
                return {"languages": [{"id": "1", "label": "English", "locale": "en", "isActive": True}]}

        self.ensure_valid_token()

        payload = {
            "query": query,
            "variables": variables or {},
        }
        headers = dict(self.headers)
        start_time = time.time()
        try:
            response = self.session.post(self.graphql_url, headers=headers, json=payload, timeout=15)
            if response.status_code == 401:
                if self.refresh_token:
                    self._perform_token_refresh()
                    headers = dict(self.headers)
                    response = self.session.post(self.graphql_url, headers=headers, json=payload, timeout=15)
                if response.status_code == 401 and self.primary_token and headers.get("Authorization") != self.primary_token:
                    headers["Authorization"] = self.primary_token
                    response = self.session.post(self.graphql_url, headers=headers, json=payload, timeout=15)

            duration_ms = int((time.time() - start_time) * 1000)

            if response.status_code >= 400:
                frappe.logger("tap_buddy_glific").error(frappe.as_json({
                    "endpoint": self.graphql_url,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }))

            response.raise_for_status()
            data = response.json() if response.text else {}
            errors = data.get("errors")
            if errors:
                record_api_failure("glific")
                raise GlificTerminalError(f"Terminal Glific Error: 200 - {_serialize_graphql_errors(errors)}")

            record_api_success("glific")
            return data.get("data", {})

        except requests.exceptions.HTTPError as e:
            record_api_failure("glific")
            status_code = getattr(e.response, "status_code", 500)
            text = getattr(e.response, "text", str(e))
            frappe.logger("tap_buddy_glific").error(f"GraphQL HTTP error: status={status_code}")
            if status_code in (400, 401, 404):
                raise GlificTerminalError(f"Terminal Glific Error: {status_code} - {text}")
            raise GlificAPIError(f"Glific API HTTP Error: {status_code} - {text}")

        except requests.exceptions.RequestException as e:
            record_api_failure("glific")
            frappe.logger("tap_buddy_glific").error(f"GraphQL request failed: {repr(e)}")
            raise GlificAPIError(f"Glific API request failed: {str(e)}")

    def _request(self, method, path, **kwargs):
        if check_circuit_breaker("glific"):
            frappe.logger("tap_buddy_glific").error("Circuit breaker is OPEN. Dropping request.")
            raise GlificAPIError("Glific circuit breaker is open. Temporarily unavailable.")

        self.ensure_valid_token()
        
        url = f"{self.base_url}{path}"
        headers = dict(self.headers)
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
            
        start_time = time.time()
        try:
            response = self.session.request(method, url, headers=headers, timeout=15, **kwargs)
            if response.status_code == 401 and self.primary_token and headers.get("Authorization") != self.primary_token:
                headers["Authorization"] = self.primary_token
                response = self.session.request(method, url, headers=headers, timeout=15, **kwargs)

            duration_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code >= 400:
                # Log endpoint + status only — response body is excluded to prevent
                # upstream API error messages from echoing sensitive values into logs.
                frappe.logger("tap_buddy_glific").error(frappe.as_json({
                    "endpoint": path,
                    "status": response.status_code,
                    "duration_ms": duration_ms,
                }))
            
            response.raise_for_status()
            record_api_success("glific")
            return response.json() if response.text else {}
            
        except requests.exceptions.HTTPError as e:
            record_api_failure("glific")
            status_code = getattr(e.response, 'status_code', 500)
            text = getattr(e.response, 'text', str(e))
            frappe.logger("tap_buddy_glific").error(f"REST HTTP error: method={method} path={path} status={status_code}")
            if status_code in (400, 401, 404):
                raise GlificTerminalError(f"Terminal Glific Error: {status_code} - {text}")
            raise GlificAPIError(f"Glific API HTTP Error: {status_code} - {text}")
            
        except requests.exceptions.RequestException as e:
            record_api_failure("glific")
            frappe.logger("tap_buddy_glific").error(f"REST request failed: method={method} path={path} error={repr(e)}")
            raise GlificAPIError(f"Glific API request failed: {str(e)}")

    def authenticate(self):
        # We can validate the token here by calling a safe endpoint
        return True

    def send_message(self, phone, message, idempotency_key=None):
                phone = normalize_phone(phone)
                contact = self.get_contact(phone)
                contact_id = _extract_contact_id(contact)
                if not contact_id:
                        created = self.create_contact({"name": phone, "phone": phone})
                        contact_id = _extract_contact_id(created)
                if not contact_id:
                        raise GlificAPIError(f"Unable to resolve Glific contact for phone {phone}")

                query = """
                mutation createAndSendMessage($input: MessageInput!) {
                    createAndSendMessage(input: $input) {
                        message { id body type insertedAt sendAt }
                        errors { key message }
                    }
                }
                """
                variables = {
                        "input": {
                                "body": message,
                                "flow": "OUTBOUND",
                                "type": "TEXT",
                                "receiverId": _coerce_glific_id(contact_id),
                        }
                }


                result = self._graphql_request(query, variables).get("createAndSendMessage") or {}
                errors = result.get("errors")
                if errors:
                        raise GlificTerminalError(f"Terminal Glific Error: 200 - {_serialize_graphql_errors(errors)}")
                return result.get("message") or {}

    def get_message(self, message_id):
                query = """
                query getMessage($id: ID!) {
                    message(id: $id) {
                        message {
                            id
                            bspMessageId
                            bspStatus
                            status
                            type
                            isHsm
                            templateId
                            params
                            body
                            flowLabel
                            groupId
                            sendAt
                            insertedAt
                            updatedAt
                            receiver { phone }
                            sender { phone }
                            contact { phone }
                        }
                        errors { key message }
                    }
                }
                """
                result = self._graphql_request(query, {"id": str(message_id)}).get("message") or {}
                errors = result.get("errors")
                if errors:
                        raise GlificTerminalError(f"Terminal Glific Error: 200 - {_serialize_graphql_errors(errors)}")
                return result.get("message") or {}

    def resend_message(self, message_id):

                message = self.get_message(message_id)
                if not message:
                        raise GlificAPIError(f"Glific message {message_id} not found")

                phone = None
                if message.get("receiver") and message["receiver"].get("phone"):
                        phone = message["receiver"]["phone"]
                elif message.get("contact") and message["contact"].get("phone"):
                        phone = message["contact"]["phone"]

                if not phone:
                        raise GlificAPIError(f"Unable to determine recipient phone for message {message_id}")

                if message.get("isHsm") and message.get("templateId"):
                        return self.send_hsm_message(
                                phone,
                                message["templateId"],
                                message.get("params") or [],
                        )

                return self.send_message(phone, message.get("body") or "")

    def send_hsm_message(self, phone, template_id, parameters=None):
                phone = normalize_phone(phone)
                contact = self.get_contact(phone)
                contact_id = _extract_contact_id(contact)
                if not contact_id:
                        created = self.create_contact({"name": phone, "phone": phone})
                        contact_id = _extract_contact_id(created)
                if not contact_id:
                        raise GlificAPIError(f"Unable to resolve Glific contact for phone {phone}")

                query = """
                mutation sendHsmMessage($receiverId: ID!, $templateId: ID!, $parameters: [String]) {
                    sendHsmMessage(receiverId: $receiverId, templateId: $templateId, parameters: $parameters) {
                        message {
                            id
                            bspMessageId
                            bspStatus
                            status
                            type
                            isHsm
                            body
                            flowLabel
                            groupId
                            sendAt
                            insertedAt
                            updatedAt
                            receiver { phone }
                            sender { phone }
                            contact { phone }
                        }
                        errors { key message }
                    }
                }
                """
                variables = {
                        "receiverId": _coerce_glific_id(contact_id),
                        "templateId": _coerce_glific_id(template_id),
                        "parameters": parameters if parameters is not None else None,
                }


                result = self._graphql_request(query, variables).get("sendHsmMessage") or {}
                errors = result.get("errors")
                if errors:
                        raise GlificTerminalError(f"Terminal Glific Error: 200 - {_serialize_graphql_errors(errors)}")
                return result.get("message") or {}

    # ------------------------------------------------------------------
    # Group & Collection Management
    # ------------------------------------------------------------------

    def get_group_collections(self):
        """
        Fetch all Group Collections from Glific.
        """
        query = """
        query {
            groups(opts: {limit: 10000}) {
                id
                label
                waGroupsCount
            }
        }
        """
        result = self._graphql_request(query)
        return result.get("groups") or []

    def get_whatsapp_groups(self):
        """
        Fetch all WhatsApp Groups and their Collection mappings from Glific.
        """
        query = """
        query {
            waGroups(opts: {limit: 10000}) {
                id
                label
                lastCommunicationAt
                groups {
                    id
                    label
                }
            }
        }
        """
        result = self._graphql_request(query)
        return result.get("waGroups") or []

    def _get_default_wa_managed_phone_id(self):
        query = """
        query {
          waManagedPhones {
            id
            phone
          }
        }
        """
        try:
            result = self._graphql_request(query)
            phones = result.get("waManagedPhones", [])
            if phones:
                return phones[0].get("id")
        except Exception as e:
            frappe.logger("tap_buddy_glific").error(f"Failed to fetch waManagedPhones: {e}")
        return None

    def send_message_to_group(self, group_id: str, message: str):
        """
        Send a text message directly to a WhatsApp Group.
        """
        query = """
        mutation sendMessageInWaGroup($input: WaMessageInput!) {
            sendMessageInWaGroup(input: $input) {
                errors {
                    key
                    message
                }
            }
        }
        """
        phone_id = self._get_default_wa_managed_phone_id()
        variables = {
            "input": {
                "waGroupId": str(_coerce_glific_id(group_id)),
                "message": message,
                "type": "TEXT"
            }
        }
        if phone_id:
            variables["input"]["waManagedPhoneId"] = phone_id

        result = self._graphql_request(query, variables).get("sendMessageInWaGroup") or {}
        errors = result.get("errors")
        if errors:
            raise GlificTerminalError(f"Terminal Glific Error: 200 - {_serialize_graphql_errors(errors)}")
        return result.get("message") or {}

    # ------------------------------------------------------------------
    # Template discovery
    # ------------------------------------------------------------------

    def get_template_by_name(self, template_name):
        """
        Look up a Glific HSM session template by its shortcode / element name.

        Results are cached on the client instance for the lifetime of the
        object (one dispatch batch) to avoid repeated GraphQL round-trips.

        Returns a dict with at minimum: ``{"id": "...", "shortcode": "...",
        "numberParameters": N, "status": "APPROVED"}``
        Raises ``GlificTerminalError`` if the template is not found or not APPROVED.
        """
        if not hasattr(self, "_template_cache"):
            self._template_cache = {}

        if template_name in self._template_cache:
            return self._template_cache[template_name]

        frappe.logger("tap_buddy_glific").info(
            f"[HSM] Looking up template shortcode='{template_name}'"
        )

        query = """
        query sessionTemplates($filter: SessionTemplateFilter, $opts: Opts) {
            sessionTemplates(filter: $filter, opts: $opts) {
                id
                label
                body
                shortcode
                status
                category
                numberParameters
                isHsm
            }
        }
        """
        data = self._graphql_request(
            query,
            {"filter": {"term": template_name}, "opts": {"limit": 10}},
        )
        templates = data.get("sessionTemplates") or []

        # Filter by exact shortcode match
        matched = [
            t for t in templates
            if (t.get("shortcode") or "").lower() == template_name.lower()
        ]

        if not matched:
            frappe.logger("tap_buddy_glific").error(
                f"[HSM] Template not found: '{template_name}'"
            )
            raise GlificTerminalError(
                f"Glific template '{template_name}' not found. "
                f"Available shortcodes: {[t.get('shortcode') for t in templates]}"
            )

        tmpl = matched[0]
        if tmpl.get("status") != "APPROVED":
            raise GlificTerminalError(
                f"Glific template '{template_name}' is not APPROVED (status={tmpl.get('status')}). "
                "Cannot send HSM messages."
            )

        frappe.logger("tap_buddy_glific").info(
            f"[HSM] Template resolved: shortcode={template_name} id={tmpl['id']} "
            f"label='{tmpl.get('label')}' params={tmpl.get('numberParameters')}"
        )
        self._template_cache[template_name] = tmpl
        return tmpl

    # ------------------------------------------------------------------
    # Contact optin
    # ------------------------------------------------------------------

    def optin_contact(self, phone, name=None):
        """
        Opt a contact in to HSM messaging via Glific's ``optinContact`` mutation.
        Required before ``sendHsmMessage`` can be used for a new contact.
        Idempotent — safe to call even if the contact is already opted in.

        Returns the updated contact dict (includes ``bspStatus``).
        """
        phone = normalize_phone(phone)
        frappe.logger("tap_buddy_glific").info(
            f"[HSM] Opting in contact phone={phone} name={name!r}"
        )
        mutation = """
        mutation optinContact($phone: String!, $name: String) {
            optinContact(phone: $phone, name: $name) {
                contact { id phone bspStatus optinTime }
                errors { key message }
            }
        }
        """
        result = self._graphql_request(mutation, {"phone": phone, "name": name or phone}).get("optinContact") or {}
        errors = result.get("errors")
        if errors:
            frappe.logger("tap_buddy_glific").warning(
                f"[HSM] optinContact errors for {phone}: {_serialize_graphql_errors(errors)}"
            )
        contact = result.get("contact") or {}
        frappe.logger("tap_buddy_glific").info(
            f"[HSM] After optin: contact id={contact.get('id')} bspStatus={contact.get('bspStatus')}"
        )
        return contact

    # ------------------------------------------------------------------
    # PTA HSM template sender
    # ------------------------------------------------------------------

    def send_pta_template(
        self,
        phone,
        parent_name,
        student_name,
        meeting_date,
        meeting_time,
        template_name="pta_meeting_alert_v2",
    ):
        """
        Send the approved PTA meeting notification HSM template.

        Parameter mapping (as approved by WhatsApp):
            {{1}} -> parent_name
            {{2}} -> student_name
            {{3}} -> meeting_date   (e.g. "28 May 2026")
            {{4}} -> meeting_time   (e.g. "10:00 AM")

        Flow:
            1. Resolve template ID from shortcode
            2. Resolve / create Glific contact
            3. Ensure contact is opted-in for HSM (idempotent)
            4. Send via sendHsmMessage
            5. Log full request + response

        Returns the Glific message dict on success.
        Raises ``GlificTerminalError`` for non-retryable errors.
        Raises ``GlificAPIError`` for transient errors.
        """
        phone_norm = normalize_phone(phone)
        parameters = [parent_name, student_name, meeting_date, meeting_time]

        frappe.logger("tap_buddy_glific").info(
            f"[PTA-HSM] Initiating send "
            f"phone={phone_norm} template={template_name} "
            f"params={parameters}"
        )

        # Step 1: Validate template exists and is approved
        tmpl = self.get_template_by_name(template_name)
        template_id = tmpl["id"]
        expected_params = tmpl.get("numberParameters", 4)

        if len(parameters) != expected_params:
            raise GlificTerminalError(
                f"Template '{template_name}' expects {expected_params} parameters "
                f"but got {len(parameters)}: {parameters}"
            )

        # Step 2: Resolve contact
        contact = self.get_contact(phone_norm)
        contact_id = _extract_contact_id(contact)
        if not contact_id:
            frappe.logger("tap_buddy_glific").info(
                f"[PTA-HSM] Contact not found for {phone_norm}, creating"
            )
            created = self.create_contact({"name": phone_norm, "phone": phone_norm})
            contact_id = _extract_contact_id(created)
        if not contact_id:
            raise GlificAPIError(
                f"[PTA-HSM] Unable to resolve Glific contact for phone {phone_norm}"
            )

        frappe.logger("tap_buddy_glific").info(
            f"[PTA-HSM] Resolved contact_id={contact_id} for phone={phone_norm}"
        )

        # Step 3: Ensure contact is opted in (HSM bspStatus)
        self.optin_contact(phone_norm)

        # Step 4: Send HSM
        query = """
        mutation sendHsmMessage($receiverId: ID!, $templateId: ID!, $parameters: [String]) {
            sendHsmMessage(receiverId: $receiverId, templateId: $templateId, parameters: $parameters) {
                message {
                    id
                    bspMessageId
                    bspStatus
                    body
                    type
                    isHsm
                    insertedAt
                    receiver { phone }
                }
                errors { key message }
            }
        }
        """
        variables = {
            "receiverId": str(contact_id),
            "templateId": str(template_id),
            "parameters": parameters,
        }

        frappe.logger("tap_buddy_glific").info(
            f"[PTA-HSM] GraphQL sendHsmMessage payload: "
            f"receiverId={contact_id} templateId={template_id} parameters={parameters}"
        )

        result = self._graphql_request(query, variables).get("sendHsmMessage") or {}
        errors = result.get("errors")

        if errors:
            err_str = _serialize_graphql_errors(errors)
            frappe.logger("tap_buddy_glific").error(
                f"[PTA-HSM] GraphQL errors for phone={phone_norm}: {err_str}"
            )
            raise GlificTerminalError(f"PTA HSM send failed: {err_str}")

        message = result.get("message") or {}
        frappe.logger("tap_buddy_glific").info(
            f"[PTA-HSM] SUCCESS phone={phone_norm} "
            f"message_id={message.get('id')} "
            f"bspMessageId={message.get('bspMessageId')} "
            f"bspStatus={message.get('bspStatus')} "
            f"insertedAt={message.get('insertedAt')}"
        )
        return message

    # ------------------------------------------------------------------
    # Smart sender: free-form with automatic HSM fallback
    # ------------------------------------------------------------------

    def send_message_with_hsm_fallback(
        self,
        phone,
        message,
        hsm_template_name=None,
        hsm_parameters=None,
        idempotency_key=None,
    ):
        """
        Attempt free-form messaging first; if the WhatsApp 24-hour session
        window is closed, automatically fall back to the HSM template.

        Args:
            phone:              Recipient phone (any format — will be normalised)
            message:            Free-form message body
            hsm_template_name:  Glific shortcode of the fallback HSM template
            hsm_parameters:     Ordered list of parameter strings for the template
            idempotency_key:    Passed to the free-form send path

        Returns:
            (message_dict, used_hsm: bool)
        """
        _24HR_WINDOW_ERROR = "24 hrs window closed"

        frappe.logger("tap_buddy_glific").info(
            f"[SEND] Attempting free-form send to phone={normalize_phone(phone)}"
        )
        try:
            msg = self.send_message(phone, message, idempotency_key=idempotency_key)
            frappe.logger("tap_buddy_glific").info(
                f"[SEND] Free-form send SUCCESS message_id={msg.get('id')}"
            )
            return msg, False

        except GlificTerminalError as exc:
            if _24HR_WINDOW_ERROR.lower() not in str(exc).lower():
                # Non-window terminal error — do not fall back, re-raise
                raise

            if not hsm_template_name or hsm_parameters is None:
                frappe.logger("tap_buddy_glific").warning(
                    f"[SEND] 24hr window closed for {phone} and no HSM fallback configured."
                )
                raise

            frappe.logger("tap_buddy_glific").info(
                f"[SEND] 24hr window closed for {phone}. "
                f"Falling back to HSM template='{hsm_template_name}' "
                f"parameters={hsm_parameters}"
            )

            # Ensure correct number of params
            tmpl = self.get_template_by_name(hsm_template_name)
            template_id = tmpl["id"]

            phone_norm = normalize_phone(phone)
            contact = self.get_contact(phone_norm)
            contact_id = _extract_contact_id(contact)
            if not contact_id:
                created = self.create_contact({"name": phone_norm, "phone": phone_norm})
                contact_id = _extract_contact_id(created)
            if not contact_id:
                raise GlificAPIError(f"Cannot resolve contact for HSM fallback: {phone_norm}")

            self.optin_contact(phone_norm)

            hsm_query = """
            mutation sendHsmMessage($receiverId: ID!, $templateId: ID!, $parameters: [String]) {
                sendHsmMessage(receiverId: $receiverId, templateId: $templateId, parameters: $parameters) {
                    message { id bspMessageId bspStatus body type isHsm insertedAt receiver { phone } }
                    errors { key message }
                }
            }
            """
            variables = {
                "receiverId": str(contact_id),
                "templateId": str(template_id),
                "parameters": hsm_parameters,
            }
            result = self._graphql_request(hsm_query, variables).get("sendHsmMessage") or {}
            errors = result.get("errors")
            if errors:
                err_str = _serialize_graphql_errors(errors)
                frappe.logger("tap_buddy_glific").error(
                    f"[SEND] HSM fallback errors for {phone_norm}: {err_str}"
                )
                raise GlificTerminalError(f"HSM fallback failed: {err_str}")

            msg = result.get("message") or {}
            frappe.logger("tap_buddy_glific").info(
                f"[SEND] HSM fallback SUCCESS phone={phone_norm} "
                f"message_id={msg.get('id')} bspStatus={msg.get('bspStatus')}"
            )
            return msg, True

    def get_contact(self, phone):

                if phone:
                    phone = normalize_phone(phone)
                query = """
                query contactByPhone($phone: String!) {
                    contactByPhone(phone: $phone) {
                        contact {
                            id
                            name
                            phone
                            status
                        }
                    }
                }
                """
                result = self._graphql_request(query, {"phone": phone}).get("contactByPhone") or {}
                return result.get("contact")

    def create_contact(self, payload):
                phone = payload.get("phone")
                if phone:
                    phone = normalize_phone(phone)
                input_payload = {
                        "name": payload.get("name") or phone,
                        "phone": phone,
                }
                fields = _coerce_glific_fields(payload.get("fields"))
                if fields:
                        input_payload["fields"] = fields

                query = """
                mutation createContact($input: ContactInput!) {
                    createContact(input: $input) {
                        contact {
                            id
                            name
                            phone
                        }
                        errors { key message }
                    }
                }
                """
                result = self._graphql_request(query, {"input": input_payload}).get("createContact") or {}
                errors = result.get("errors")
                if errors:
                        raise GlificTerminalError(f"Terminal Glific Error: 200 - {_serialize_graphql_errors(errors)}")
                return result.get("contact") or {}

    def update_contact(self, contact_id, payload):
                phone = payload.get("phone")
                if phone:
                    phone = normalize_phone(phone)
                input_payload = {
                        "name": payload.get("name") or phone,
                        "phone": phone,
                }
                fields = _coerce_glific_fields(payload.get("fields"))
                if fields:
                        input_payload["fields"] = fields

                query = """
                mutation updateContact($id: ID!, $input: ContactInput!) {
                    updateContact(id: $id, input: $input) {
                        contact {
                            id
                            name
                            phone
                        }
                        errors { key message }
                    }
                }
                """
                result = self._graphql_request(
                        query,
                        {"id": _coerce_glific_id(contact_id), "input": input_payload},
                ).get("updateContact") or {}
                errors = result.get("errors")
                if errors:
                        raise GlificTerminalError(f"Terminal Glific Error: 200 - {_serialize_graphql_errors(errors)}")
                return result.get("contact") or {}

    def upsert_contact(self, payload):
        phone = payload.get("phone")
        if not phone:
            raise GlificAPIError("Contact payload missing phone")
        phone = normalize_phone(phone)
        payload["phone"] = phone
        existing = self.get_contact(phone)
        contact_id = _extract_contact_id(existing)
        if contact_id:
            return self.update_contact(contact_id, payload)
        return self.create_contact(payload)

    def add_contact_to_group(self, group_id, contact_id):
                query = """
                mutation createContactGroup($input: ContactGroupInput!) {
                    createContactGroup(input: $input) {
                        contactGroup {
                            id
                            contact { id }
                            group { id label }
                        }
                        errors { key message }
                    }
                }
                """
                variables = {
                        "input": {
                                "groupId": _coerce_glific_id(group_id),
                                "contactId": _coerce_glific_id(contact_id),
                        }
                }
                result = self._graphql_request(query, variables).get("createContactGroup") or {}
                errors = result.get("errors")
                if errors:
                        raise GlificTerminalError(f"Terminal Glific Error: 200 - {_serialize_graphql_errors(errors)}")
                return result.get("contactGroup") or {}

    def get_groups(self, params=None):
                params = params or {}
                page = max(int(params.get("page", 1)), 1)
                limit = max(int(params.get("limit", 100)), 1)
                opts = {
                        "limit": limit,
                        "offset": (page - 1) * limit,
                        "order": "ASC",
                }
                filter_payload = {}
                if params.get("label"):
                        filter_payload["label"] = params["label"]

                query = """
                query groups($filter: GroupFilter, $opts: Opts) {
                    groups(filter: $filter, opts: $opts) {
                        id
                        label
                        isRestricted
                        contactsCount
                        usersCount
                    }
                }
                """
                result = self._graphql_request(query, {"filter": filter_payload, "opts": opts})
                groups = []
                for group in result.get("groups") or []:
                        item = dict(group)
                        item.setdefault("name", item.get("label"))
                        groups.append(item)
                return {
                        "data": groups,
                        "metadata": {"next_page": page + 1 if len(groups) == limit else None},
                }

    def create_group(self, payload):
                input_payload = {
                        "label": payload.get("label") or payload.get("name"),
                }
                if payload.get("isRestricted") is not None:
                        input_payload["isRestricted"] = payload.get("isRestricted")

                query = """
                mutation createGroup($input: GroupInput!) {
                    createGroup(input: $input) {
                        group {
                            id
                            label
                            isRestricted
                        }
                        errors { key message }
                    }
                }
                """
                result = self._graphql_request(query, {"input": input_payload}).get("createGroup") or {}
                errors = result.get("errors")
                if errors:
                        raise GlificTerminalError(f"Terminal Glific Error: 200 - {_serialize_graphql_errors(errors)}")
                group = result.get("group") or {}
                if group:
                        group.setdefault("name", group.get("label"))
                return group

    # ------------------------------------------------------------------
    # HSM Template management
    # ------------------------------------------------------------------

    def get_languages(self):
        """Return available languages from Glific with their IDs."""
        query = """
        query languages($filter: LanguageFilter, $opts: Opts) {
            languages(filter: $filter, opts: $opts) {
                id
                label
                locale
                isActive
            }
        }
        """
        result = self._graphql_request(query, {"filter": {}, "opts": {"limit": 50}})
        return result.get("languages") or []

    def create_hsm_template(
        self,
        label: str,
        shortcode: str,
        body: str,
        language: str = "English",
        category: str = "UTILITY",
    ) -> dict:
        """Register a new HSM template in Glific via createSessionTemplate.

        Returns dict with: id, label, shortcode, body, status.
        NOTE: Status will be PENDING until WhatsApp/Meta approves (24-48h).
        """
        langs = self.get_languages()
        lang_map = {l["label"].lower(): l["id"] for l in langs}
        lang_id = lang_map.get(language.lower())
        if not lang_id:
            lang_id = langs[0]["id"] if langs else "1"
            frappe.logger("tap_buddy_glific").warning(
                f"[HSM-CREATE] Language '{language}' not found, using id={lang_id}. "
                f"Available: {list(lang_map.keys())}"
            )

        frappe.logger("tap_buddy_glific").info(
            f"[HSM-CREATE] Creating template shortcode='{shortcode}' "
            f"language={language}({lang_id}) category={category}"
        )

        mutation = """
        mutation createSessionTemplate($input: SessionTemplateInput!) {
            createSessionTemplate(input: $input) {
                sessionTemplate {
                    id
                    label
                    body
                    shortcode
                    status
                    category
                    isHsm
                    numberParameters
                    language { id label }
                }
                errors { key message }
            }
        }
        """
        variables = {
            "input": {
                "label":      label,
                "shortcode":  shortcode.lower().replace(" ", "_"),
                "body":       body,
                "languageId": str(lang_id),
                "type":       "TEXT",
                "category":   category,
                "isHsm":      True,
                "example":    "test",
            }
        }

        result = self._graphql_request(mutation, variables).get("createSessionTemplate") or {}
        errors = result.get("errors")
        if errors:
            err_str = _serialize_graphql_errors(errors)
            frappe.logger("tap_buddy_glific").error(
                f"[HSM-CREATE] createSessionTemplate errors: {err_str}"
            )
            raise GlificTerminalError(f"HSM template creation failed: {err_str}")

        tmpl = result.get("sessionTemplate") or {}
        frappe.logger("tap_buddy_glific").info(
            f"[HSM-CREATE] Template created id={tmpl.get('id')} "
            f"shortcode={tmpl.get('shortcode')} status={tmpl.get('status')}"
        )
        return tmpl

    # ------------------------------------------------------------------
    # Flow execution
    # ------------------------------------------------------------------

    def get_flows(self, is_active=True, limit=1000):
        """
        Fetch flows from Glific.
        """
        query = """
        query flows($filter: FlowFilter, $opts: Opts) {
            flows(filter: $filter, opts: $opts) {
                id
                name
                flowType
                isActive
                isBackground
            }
        }
        """
        variables = {
            "filter": {"isActive": is_active},
            "opts": {"limit": limit}
        }
        result = self._graphql_request(query, variables)
        return result.get("flows") or []

    def start_contact_flow(self, phone, flow_id, default_results=None):

        phone = normalize_phone(phone)
        contact = self.get_contact(phone)
        contact_id = _extract_contact_id(contact)
        if not contact_id:
            created = self.create_contact({"name": phone, "phone": phone})
            contact_id = _extract_contact_id(created)
        if not contact_id:
            raise GlificAPIError(f"Unable to resolve Glific contact for phone {phone}")

        mutation = """
        mutation startContactFlow($contactId: ID!, $flowId: ID!, $defaultResults: Json) {
            startContactFlow(contactId: $contactId, flowId: $flowId, defaultResults: $defaultResults) {
                success
                errors { key message }
            }
        }
        """
        variables = {
            "contactId": _coerce_glific_id(contact_id),
            "flowId": _coerce_glific_id(flow_id),
        }
        if default_results is not None:
            # Glific requires Json scalar, which is passed as a string or raw json depending on client
            # Let's pass it as a JSON string
            variables["defaultResults"] = json.dumps(default_results) if isinstance(default_results, dict) else default_results

        result = self._graphql_request(mutation, variables).get("startContactFlow") or {}
        errors = result.get("errors")
        if errors:
            raise GlificTerminalError(f"Terminal Glific Error: startContactFlow - {_serialize_graphql_errors(errors)}")
        
        return result

    def start_wa_group_flow(self, wa_group_id, flow_id):
        mutation = """
        mutation startWaGroupFlow($waGroupId: ID!, $flowId: ID!) {
            startWaGroupFlow(waGroupId: $waGroupId, flowId: $flowId) {
                success
                errors { key message }
            }
        }
        """
        variables = {
            "waGroupId": str(_coerce_glific_id(wa_group_id)),
            "flowId": str(_coerce_glific_id(flow_id))
        }
        result = self._graphql_request(mutation, variables).get("startWaGroupFlow") or {}
        errors = result.get("errors")
        if errors:
            raise GlificTerminalError(f"Terminal Glific Error: startWaGroupFlow - {_serialize_graphql_errors(errors)}")
        return result

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
