# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class LibraryMember(Document):
	def before_save(self):
		self.set_full_name()
		self.generate_email_if_missing()

	def set_full_name(self):
		"""Set full name from first and last name"""
		first = (self.first_name or "").strip()
		last = (self.last_name or "").strip()

		if first and last:
			self.full_name = f"{first} {last}"
		elif first:
			self.full_name = first
		elif last:
			self.full_name = last
		else:
			self.full_name = ""

	def generate_email_if_missing(self):
		"""Generate email address if not provided"""
		if not self.email_address:
			first = (self.first_name or "").strip().lower()
			last = (self.last_name or "").strip().lower()

			if first or last:
				# Use available name parts
				email_base = first + last
				if not email_base:
					# Fallback to member ID if no names
					email_base = "member"
				self.email_address = email_base + "@fakemail.com"
			else:
				# No names provided, use member ID
				self.email_address = "member@fakemail.com"

	
