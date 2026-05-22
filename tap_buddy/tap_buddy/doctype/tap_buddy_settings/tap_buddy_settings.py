# Copyright (c) 2026, Nigam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from datetime import datetime

class TAPBuddySettings(Document):
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
		if not self.batch_size:
			return
		
		if self.batch_size < 1 or self.batch_size > 200:
			frappe.throw("Batch Size must be between 1 and 200")
