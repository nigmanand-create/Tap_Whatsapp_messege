# Copyright (c) 2026, Nigam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
import requests
from datetime import datetime
from frappe.utils import now_datetime
from dateutil import parser

class TAPBuddySettings(Document):
	glific_url: str | None
	glific_token: str | None
	glific_access_token: str | None
	glific_refresh_token: str | None
	glific_token_expiry: str | None
	glific_phone_number: str | None
	sync_mode_fallback: int | None
	webhook_enabled: int | None
	webhook_secret: str | None
	webhook_signature_header: str | None
	batch_size: int | None
	rate_limit: int | None
	retry_count: int | None
	dispatch_start_hour: str | None
	dispatch_end_hour: str | None

	def validate(self):
		self.validate_dispatch_hours()
		self.validate_batch_size()
		self.validate_glific_tokens()

	def validate_glific_tokens(self):
		if self.get_password("glific_access_token") and not self.get_password("glific_refresh_token"):
			frappe.throw("A Refresh Token must be provided when an Access Token is set. Missing refresh token will cause automated rotation to fail permanently.")

	def validate_dispatch_hours(self):
		if not self.dispatch_start_hour or not self.dispatch_end_hour:
			return

		start = datetime.strptime(str(self.dispatch_start_hour), "%H:%M:%S")
		end = datetime.strptime(str(self.dispatch_end_hour), "%H:%M:%S")

		if start >= end:
			frappe.throw("Dispatch Start Time must be strictly before Dispatch End Time")

	def validate_batch_size(self):
		batch_size = self.batch_size
		if batch_size is None:
			return
		
		if int(batch_size) < 1 or int(batch_size) > 200:
			frappe.throw("Batch Size must be between 1 and 200")

@frappe.whitelist()
def bootstrap_glific_session(phone, password):
	settings = frappe.get_single("TAP Buddy Settings")
	if not settings.glific_url:
		frappe.throw("Please save the Glific URL before bootstrapping credentials.")

	url = settings.glific_url.rstrip("/") + "/api/v1/session"
	try:
		res = requests.post(
			url,
			json={"user": {"phone": phone, "password": password}},
			headers={"Content-Type": "application/json"},
			timeout=15
		)
		if res.status_code == 401:
			return {"status": "failed", "message": "Invalid phone number or password."}
		res.raise_for_status()
		data = res.json().get("data", {})
		
		# Extract tokens
		access_token = data.get("access_token")
		refresh_token = data.get("renewal_token") or data.get("refresh_token")
		expiry = data.get("token_expiry_time") or data.get("expires_at")
		
		if not access_token or not refresh_token:
			return {"status": "failed", "message": "Glific returned an invalid payload (missing tokens)."}
		
		# Save safely
		settings.glific_access_token = access_token
		settings.glific_refresh_token = refresh_token
		settings.glific_token_expiry = expiry
		settings.save(ignore_permissions=True)
		frappe.db.commit()
		
		# Log success
		_log_auth_event("Refresh Succeeded", "Initial bootstrap completed successfully.", "Info", _calculate_mins_to_expiry(expiry))
		
		return {"status": "success", "message": "Credentials successfully bootstrapped and stored securely."}
	except Exception as e:
		_log_auth_event("Refresh Failed", f"Bootstrap failed: {str(e)}", "Error", 0)
		return {"status": "error", "message": f"Connection failed: {str(e)}"}

@frappe.whitelist()
def test_glific_connection():
	from tap_buddy.services.glific_client import GlificClient
	try:
		client = GlificClient()
		result = client._graphql_request("query { users { id name } }")
		if "users" in result:
			return {"status": "success", "message": "Successfully connected to Glific API."}
		return {"status": "failed", "message": "API connected but returned unexpected response format."}
	except Exception as e:
		return {"status": "error", "message": f"Connection Test Failed: {str(e)}"}

@frappe.whitelist()
def get_auth_dashboard_metrics():
	settings = frappe.get_single("TAP Buddy Settings")
	access_token = settings.get_password("glific_access_token")
	refresh_token = settings.get_password("glific_refresh_token")
	expiry_str = settings.glific_token_expiry
	
	status = "Healthy"
	severity = "Green"
	mins_to_expiry = None
	
	if not access_token:
		status = "Not Configured"
		severity = "Red"
	elif not refresh_token:
		status = "Missing Refresh Token"
		severity = "Red"
	elif expiry_str:
		mins_to_expiry = _calculate_mins_to_expiry(expiry_str)
		if mins_to_expiry < 0:
			status = "Token Expired"
			severity = "Red"
		elif mins_to_expiry < 30:
			status = "Token Expiring Soon"
			severity = "Yellow"
	
	# Fetch last event from log
	last_event = frappe.get_all("Glific Auth Log", fields=["event", "message", "timestamp", "severity"], order_by="timestamp desc", limit=1)
	last_refresh_time = None
	last_error = None
	
	if last_event:
		log = last_event[0]
		if log.event == "Refresh Failed" or log.severity in ("Error", "Critical"):
			status = "Refresh Failed"
			severity = "Red"
			last_error = log.message
		elif log.event == "Refresh Succeeded":
			last_refresh_time = log.timestamp
			
	return {
		"status": status,
		"severity": severity,
		"mins_to_expiry": mins_to_expiry,
		"last_refresh_time": last_refresh_time,
		"last_error": last_error,
		"has_refresh_token": bool(refresh_token)
	}

def _calculate_mins_to_expiry(expiry_str):
	if not expiry_str: return 0
	try:
		expiry_dt = parser.parse(expiry_str)
		now = datetime.now(expiry_dt.tzinfo)
		return int((expiry_dt - now).total_seconds() / 60)
	except Exception:
		return 0

def _log_auth_event(event, message, severity, countdown):
	try:
		doc = frappe.get_doc({
			"doctype": "Glific Auth Log",
			"event": event,
			"message": str(message)[:1000],
			"severity": severity,
			"expiry_countdown": countdown or 0,
			"timestamp": frappe.utils.now_datetime()
		})
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
	except Exception:
		pass # fail silently if log insertion fails

def scheduled_health_check():
	settings = frappe.get_single("TAP Buddy Settings")
	access_token = settings.get_password("glific_access_token")
	refresh_token = settings.get_password("glific_refresh_token")
	
	if not access_token:
		return
	if not refresh_token:
		_log_auth_event("Health Check", "Missing refresh token. Token rotation is broken.", "Error", 0)
		return
		
	mins_to_expiry = _calculate_mins_to_expiry(settings.glific_token_expiry)
	if mins_to_expiry < 0:
		_log_auth_event("Health Check", "Token has expired.", "Critical", mins_to_expiry)
	elif mins_to_expiry < 30:
		_log_auth_event("Health Check", "Token expiring soon.", "Warning", mins_to_expiry)
	else:
		_log_auth_event("Health Check", "Tokens are healthy.", "Info", mins_to_expiry)
