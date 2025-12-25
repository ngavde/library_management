# Copyright (c) 2023, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate

class Publisher(Document):
	def validate(self):
		self.validate_founded_year()
		self.validate_email()

	def validate_founded_year(self):
		"""Validate founded year"""
		if self.founded_year:
			current_year = getdate(today()).year
			if self.founded_year > current_year:
				frappe.throw("Founded year cannot be in the future")
			if self.founded_year < 1400:  # Reasonable lower limit
				frappe.throw("Founded year seems too old")

	def validate_email(self):
		"""Validate email format"""
		if self.email:
			import re
			email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
			if not re.match(email_pattern, self.email):
				frappe.throw("Invalid email format")

	def get_books_count(self):
		"""Get total number of books published by this publisher"""
		return frappe.db.count('Book', {'publisher': self.name})

	def get_popular_books(self, limit=10):
		"""Get most popular books by this publisher"""
		books = frappe.db.sql("""
			SELECT b.name, b.title, b.author, COUNT(t.name) as issue_count
			FROM `tabBook` b
			LEFT JOIN `tabLibrary Transaction` t ON b.name = t.book
			WHERE b.publisher = %s
			GROUP BY b.name
			ORDER BY issue_count DESC
			LIMIT %s
		""", [self.name, limit], as_dict=True)

		return books

	@frappe.whitelist()
	def get_publisher_stats(self):
		"""Get comprehensive publisher statistics"""
		stats = {
			'total_books': self.get_books_count(),
			'popular_books': self.get_popular_books()
		}

		# Get books by category
		category_stats = frappe.db.sql("""
			SELECT bc.name as category, COUNT(b.name) as book_count
			FROM `tabBook` b
			LEFT JOIN `tabBook Category` bc ON b.category = bc.name
			WHERE b.publisher = %s
			GROUP BY b.category
			ORDER BY book_count DESC
		""", [self.name], as_dict=True)

		stats['books_by_category'] = category_stats

		return stats