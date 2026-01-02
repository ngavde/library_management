# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class LibraryMember(Document):
	def before_save(self):
		first = self.first_name
		last = self.last_name
		self.email_address = self.first_name.lower() + self.last_name.lower() + "@fakemail.com"

	
