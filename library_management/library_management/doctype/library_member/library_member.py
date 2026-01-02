# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
<<<<<<< HEAD
from frappe.utils import validate_email_address, today, getdate

class LibraryMember(Document):
	def validate(self):
		self.validate_email()
		self.validate_phone()
		self.validate_member_type()
		self.set_full_name()

	def validate_email(self):
		"""Validate email address format"""
		if self.email_address:
			try:
				validate_email_address(self.email_address, throw=True)
			except frappe.InvalidEmailAddressError:
				frappe.throw("Please enter a valid email address")

	def validate_phone(self):
		"""Validate phone number format"""
		if self.phone:
			# Remove spaces, dashes, and parentheses
			cleaned_phone = self.phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")

			# Check if it contains only digits and + symbol
			if not cleaned_phone.replace("+", "").isdigit():
				frappe.throw("Phone number should contain only digits")

			# Check length (considering international format)
			if len(cleaned_phone.replace("+", "")) < 7 or len(cleaned_phone.replace("+", "")) > 15:
				frappe.throw("Phone number length should be between 7 and 15 digits")

	def validate_member_type(self):
		"""Set default member type if not specified"""
		if not self.member_type:
			from library_management.library_management.doctype.member_type.member_type import get_default_member_type
			self.member_type = get_default_member_type()

	def set_full_name(self):
		"""Set full name from first and last name"""
		if self.first_name or self.last_name:
			name_parts = []
			if self.first_name:
				name_parts.append(self.first_name)
			if self.last_name:
				name_parts.append(self.last_name)
			self.full_name = " ".join(name_parts)

	def before_save(self):
		"""Generate email if not provided"""
		if not self.email_address and self.first_name and self.last_name:
			# Generate email from name if not provided
			email_prefix = (self.first_name.lower() + self.last_name.lower()).replace(" ", "")
			self.email_address = f"{email_prefix}@library.local"

	def get_issued_books(self):
		"""Get currently issued books for this member"""
		issued_books = frappe.get_all('Library Transaction',
			filters={
				'member': self.name,
				'status': 'Issued',
				'docstatus': 1
			},
			fields=['book', 'date', 'due_date', 'name'],
			order_by='date desc'
		)

		return issued_books

	def get_reading_history(self, limit=10):
		"""Get reading history for this member"""
		history = frappe.get_all('Library Transaction',
			filters={
				'member': self.name,
				'status': 'Returned',
				'docstatus': 1
			},
			fields=['book', 'date', 'due_date', 'fine_amount'],
			order_by='date desc',
			limit=limit
		)

		return history

	def get_overdue_books(self):
		"""Get overdue books for this member"""
		overdue_books = frappe.db.sql("""
			SELECT book, due_date, DATEDIFF(CURDATE(), due_date) as days_overdue
			FROM `tabLibrary Transaction`
			WHERE member = %s AND status = 'Issued' AND docstatus = 1 AND due_date < CURDATE()
			ORDER BY due_date ASC
		""", [self.name], as_dict=True)

		return overdue_books

	def calculate_total_fine(self):
		"""Calculate total outstanding fine"""
		total_fine = frappe.db.sql("""
			SELECT SUM(fine_amount) as total_fine
			FROM `tabLibrary Transaction`
			WHERE member = %s AND fine_amount > 0 AND fine_paid = 0 AND docstatus = 1
		""", [self.name])

		return total_fine[0][0] if total_fine and total_fine[0][0] else 0

	@frappe.whitelist()
	def get_member_stats(self):
		"""Get comprehensive member statistics"""
		stats = {
			'issued_books': len(self.get_issued_books()),
			'overdue_books': len(self.get_overdue_books()),
			'total_fine': self.calculate_total_fine(),
			'books_read': frappe.db.count('Library Transaction', {
				'member': self.name,
				'status': 'Returned',
				'docstatus': 1
			})
		}

		# Get favorite categories
		favorite_categories = frappe.db.sql("""
			SELECT bc.category_name, COUNT(*) as count
			FROM `tabLibrary Transaction` lt
			JOIN `tabBook` b ON lt.book = b.name
			JOIN `tabBook Category` bc ON b.category = bc.name
			WHERE lt.member = %s AND lt.docstatus = 1
			GROUP BY b.category
			ORDER BY count DESC
			LIMIT 5
		""", [self.name], as_dict=True)

		stats['favorite_categories'] = favorite_categories

		return stats

	def can_issue_book(self):
		"""Check if member can issue more books"""
		if self.disabled:
			return False, "Member account is disabled"

		current_books = len(self.get_issued_books())

		if self.member_type:
			member_type = frappe.get_doc("Member Type", self.member_type)
			max_allowed = member_type.max_books_allowed
		else:
			# Default limit from settings
			settings = frappe.get_single("Library Settings")
			max_allowed = settings.maximum_number_of_issued_articles or 5

		if current_books >= max_allowed:
			return False, f"Maximum book limit ({max_allowed}) reached"

		# Check for overdue books
		overdue_books = self.get_overdue_books()
		if overdue_books:
			return False, f"You have {len(overdue_books)} overdue book(s). Please return them first."

		# Check for outstanding fines
		total_fine = self.calculate_total_fine()
		if total_fine > 0:
			return False, f"You have outstanding fines of ${total_fine}. Please pay to continue borrowing."

		return True, "Eligible to borrow books"
=======

class LibraryMember(Document):
	def before_save(self):
		first = self.first_name
		last = self.last_name
		self.email_address = self.first_name.lower() + self.last_name.lower() + "@fakemail.com"

	
>>>>>>> 77745fb (Changes)
