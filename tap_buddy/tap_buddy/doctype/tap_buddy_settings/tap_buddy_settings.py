# Copyright (c) 2026, Nigam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime

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
