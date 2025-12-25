# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate, add_days

class LibraryTransaction(Document):
	def validate(self):
		self.validate_member_eligibility()
		self.validate_book_availability()
		self.validate_return_permission()
		self.set_due_date()

	def validate_member_eligibility(self):
		"""Validate member eligibility for borrowing"""
		if self.status == "Issued":
			member = frappe.get_doc("Library Member", self.member)

			# Check if member is active
			if member.disabled:
				frappe.throw("Cannot issue book to inactive member")

			# Get member type limits
			if member.member_type:
				member_type = frappe.get_doc("Member Type", member.member_type)

				# Check current books issued
				current_books = frappe.db.count('Library Transaction', {
					'member': self.member,
					'status': 'Issued',
					'docstatus': 1
				})

				if current_books >= member_type.max_books_allowed:
					frappe.throw(f"Member has reached maximum limit of {member_type.max_books_allowed} books")

	def validate_book_availability(self):
		"""Validate book is available for issue"""
		if self.status == "Issued":
			book = frappe.get_doc("Book", self.book)

			if not book.is_available_for_issue():
				frappe.throw("Book is not available for issue")

	def validate_return_permission(self):
		"""Validate only the borrower can return the book"""
		if self.status == "Returned":
			last_issue = frappe.db.get_value('Library Transaction',
				filters={
					'book': self.book,
					'status': 'Issued',
					'docstatus': 1
				},
				fieldname=['member', 'name'],
				order_by='creation desc'
			)

			if last_issue and last_issue[0] != self.member:
				frappe.throw(f"Only {last_issue[0]} can return this book")

	def set_due_date(self):
		"""Set due date based on member type"""
		if self.status == "Issued" and not self.due_date:
			member = frappe.get_doc("Library Member", self.member)

			if member.member_type:
				member_type = frappe.get_doc("Member Type", member.member_type)
				self.due_date = add_days(self.date, member_type.loan_period_days)
			else:
				# Default loan period from settings
				settings = frappe.get_single("Library Settings")
				self.due_date = add_days(self.date, settings.loan_period or 14)

	def before_submit(self):
		"""Actions before submitting transaction"""
		if self.status == "Issued":
			self.issue_book()
		elif self.status == "Returned":
			self.return_book()

	def issue_book(self):
		"""Process book issue"""
		# Update book availability
		book = frappe.get_doc("Book", self.book)
		book.available_copies = max(0, book.available_copies - 1)
		if book.available_copies == 0:
			book.status = "Issued"
		book.save()

		# Update member history
		self.update_member_history("Issued")

	def return_book(self):
		"""Process book return"""
		# Update book availability
		book = frappe.get_doc("Book", self.book)
		book.available_copies = min(book.total_copies, book.available_copies + 1)
		if book.available_copies > 0:
			book.status = "Available"
		book.save()

		# Calculate fine if overdue
		self.calculate_fine()

		# Update member history
		self.update_member_history("Returned")

	def calculate_fine(self):
		"""Calculate fine for overdue books"""
		if not self.due_date:
			return

		days_overdue = (getdate(today()) - getdate(self.due_date)).days

		if days_overdue > 0:
			member = frappe.get_doc("Library Member", self.member)
			if member.member_type:
				member_type = frappe.get_doc("Member Type", member.member_type)
				fine_per_day = member_type.late_fee_per_day
			else:
				# Default fine from settings
				settings = frappe.get_single("Library Settings")
				fine_per_day = settings.late_fee_per_day or 1.0

			self.fine_amount = days_overdue * fine_per_day
			self.days_overdue = days_overdue

	def update_member_history(self, status):
		"""Update member transaction history"""
		# Check if member history exists
		member_history = frappe.db.exists('Library Member History', {'member_name': self.member})

		if member_history:
			doc = frappe.get_doc("Library Member History", member_history)
		else:
			doc = frappe.new_doc('Library Member History')
			doc.member_name = self.member

		doc.append("transaction_history", {
			"book": self.book,
			"author": self.author,
			"isbn": self.isbn,
			"transaction_date": self.date,
			"transaction_status": status,
			"due_date": self.due_date,
			"fine_amount": self.fine_amount or 0
		})
		doc.save()

	@frappe.whitelist()
	def renew_book(self, renewal_period=None):
		"""Renew book for additional period"""
		if self.status != "Issued":
			frappe.throw("Can only renew issued books")

		member = frappe.get_doc("Library Member", self.member)

		# Check renewal eligibility
		if member.member_type:
			member_type = frappe.get_doc("Member Type", member.member_type)

			if not member_type.can_renew_online:
				frappe.throw("Online renewal not allowed for your membership type")

			# Check renewal count
			renewal_count = frappe.db.count('Library Transaction', {
				'book': self.book,
				'member': self.member,
				'transaction_type': 'Renewal',
				'docstatus': 1
			})

			if renewal_count >= member_type.max_renewals_allowed:
				frappe.throw(f"Maximum {member_type.max_renewals_allowed} renewals allowed")

			renewal_days = renewal_period or member_type.renewal_period_days
		else:
			renewal_days = renewal_period or 7

		# Create renewal transaction
		renewal = frappe.new_doc('Library Transaction')
		renewal.update({
			'book': self.book,
			'member': self.member,
			'transaction_type': 'Renewal',
			'date': today(),
			'due_date': add_days(self.due_date, renewal_days),
			'status': 'Renewed'
		})
		renewal.submit()

		# Update current transaction due date
		self.due_date = renewal.due_date
		self.save()

		return renewal