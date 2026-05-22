# Copyright (c) 2026, Nigam and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
	from frappe.types import DF

class SchoolGroup(Document):
	is_active: "DF.Check"
	members: list[Any]

	def validate(self):
		if not self.members:
			frappe.throw("A School Group must have at least one school member.")

	def get_active_schools(self):
		if not self.is_active:
			return []
		return [m.school for m in self.members]
