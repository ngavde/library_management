# Copyright (c) 2023, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
import pymysql

class Book(Document):
	def validate(self):
		self.validate_isbn()
		self.validate_copies()
		self.set_available_copies()

	def validate_isbn(self):
		"""Validate ISBN format"""
		if self.isbn:
			# Remove spaces and hyphens for validation
			isbn_clean = self.isbn.replace("-", "").replace(" ", "")
			if len(isbn_clean) != 10 or not isbn_clean.replace("X", "").isdigit():
				frappe.throw("Invalid ISBN-10 format")

		if self.isbn13:
			# Remove spaces and hyphens for validation
			isbn13_clean = self.isbn13.replace("-", "").replace(" ", "")
			if len(isbn13_clean) != 13 or not isbn13_clean.isdigit():
				frappe.throw("Invalid ISBN-13 format")

	def validate_copies(self):
		"""Validate that total copies is not less than issued copies"""
		if self.total_copies < 0:
			frappe.throw("Total copies cannot be negative")

		# Check if reducing total copies below issued copies
		if not self.is_new():
			issued_copies = self.get_issued_copies()
			if self.total_copies < issued_copies:
				frappe.throw(f"Cannot reduce total copies below {issued_copies} issued copies")

	def set_available_copies(self):
		"""Calculate and set available copies"""
		issued_copies = self.get_issued_copies()
		self.available_copies = self.total_copies - issued_copies

	def get_issued_copies(self):
		"""Get number of currently issued copies"""
		try:
			issued_count = frappe.db.count('Library Transaction', {
				'book': self.name,
				'status': 'Issued',
				'docstatus': 1
			})
			return issued_count or 0
		except (pymysql.err.OperationalError, Exception) as e:
			# Handle case where book field doesn't exist yet or database schema is not updated
			if "Unknown column 'book'" in str(e):
				frappe.log_error(f"Book field not found in Library Transaction: {str(e)}")
			return 0

	def get_average_rating(self):
		"""Get average rating from book reviews"""
		try:
			avg_rating = frappe.db.sql("""
				SELECT AVG(rating)
				FROM `tabBook Review`
				WHERE book = %s AND docstatus = 1
			""", [self.name])

			return flt(avg_rating[0][0]) if avg_rating and avg_rating[0][0] else 0
		except (pymysql.err.OperationalError, Exception) as e:
			# Handle case where book field doesn't exist yet
			if "Unknown column 'book'" in str(e):
				frappe.log_error(f"Book field not found in Book Review: {str(e)}")
			return 0

	def get_total_reviews(self):
		"""Get total number of reviews"""
		try:
			return frappe.db.count('Book Review', {
				'book': self.name,
				'docstatus': 1
			})
		except (pymysql.err.OperationalError, Exception) as e:
			# Handle case where book field doesn't exist yet
			if "Unknown column 'book'" in str(e):
				frappe.log_error(f"Book field not found in Book Review: {str(e)}")
			return 0

	def is_available_for_issue(self):
		"""Check if book is available for issue"""
		return self.status == "Available" and self.available_copies > 0

	@frappe.whitelist()
	def update_availability_status(self):
		"""Update book status based on available copies"""
		if self.available_copies <= 0:
			self.status = "Issued"
		elif self.available_copies > 0 and self.status == "Issued":
			self.status = "Available"
		self.save()

def get_books_by_category(category):
	"""Get all books in a specific category"""
	return frappe.get_all('Book',
		filters={'category': category, 'status': ['!=', 'Lost']},
		fields=['name', 'title', 'author', 'available_copies']
	)

def get_popular_books(limit=10):
	"""Get most popular books based on issue count"""
	popular_books = frappe.db.sql("""
		SELECT b.name, b.title, b.author, COUNT(t.name) as issue_count
		FROM `tabBook` b
		LEFT JOIN `tabLibrary Transaction` t ON b.name = t.book
		WHERE b.status != 'Lost'
		GROUP BY b.name
		ORDER BY issue_count DESC
		LIMIT %s
	""", [limit], as_dict=True)

	return popular_books