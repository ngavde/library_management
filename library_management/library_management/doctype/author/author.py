# Copyright (c) 2023, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate

class Author(Document):
	def validate(self):
		self.validate_dates()
		self.set_full_name()

	def validate_dates(self):
		"""Validate birth and death dates"""
		if self.birth_date and getdate(self.birth_date) > getdate(today()):
			frappe.throw("Birth date cannot be in the future")

		if self.death_date and getdate(self.death_date) > getdate(today()):
			frappe.throw("Death date cannot be in the future")

		if self.birth_date and self.death_date:
			if getdate(self.death_date) < getdate(self.birth_date):
				frappe.throw("Death date cannot be before birth date")

	def set_full_name(self):
		"""Set full name from first and last name if not provided"""
		if not self.full_name and (self.first_name or self.last_name):
			name_parts = []
			if self.first_name:
				name_parts.append(self.first_name)
			if self.last_name:
				name_parts.append(self.last_name)
			self.full_name = " ".join(name_parts)

	def get_books_count(self):
		"""Get total number of books by this author"""
		return frappe.db.count('Book', {'author': self.name})

	def get_popular_books(self, limit=5):
		"""Get most popular books by this author"""
		books = frappe.db.sql("""
			SELECT b.name, b.title, COUNT(t.name) as issue_count
			FROM `tabBook` b
			LEFT JOIN `tabLibrary Transaction` t ON b.name = t.book
			WHERE b.author = %s
			GROUP BY b.name
			ORDER BY issue_count DESC
			LIMIT %s
		""", [self.name, limit], as_dict=True)

		return books

	@frappe.whitelist()
	def get_author_stats(self):
		"""Get comprehensive author statistics"""
		stats = {
			'total_books': self.get_books_count(),
			'popular_books': self.get_popular_books()
		}

		# Get average rating across all books
		avg_rating = frappe.db.sql("""
			SELECT AVG(br.rating)
			FROM `tabBook Review` br
			INNER JOIN `tabBook` b ON br.book = b.name
			WHERE b.author = %s AND br.docstatus = 1
		""", [self.name])

		stats['average_rating'] = avg_rating[0][0] if avg_rating and avg_rating[0][0] else 0

		return stats