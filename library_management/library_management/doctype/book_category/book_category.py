# Copyright (c) 2023, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.utils.nestedset import NestedSet

class BookCategory(NestedSet):
	def validate(self):
		self.validate_category_code()
		self.validate_parent_category()

	def validate_category_code(self):
		"""Validate category code format"""
		if self.category_code:
			# Remove spaces and convert to uppercase
			self.category_code = self.category_code.replace(" ", "").upper()

			# Check for valid format (alphanumeric)
			if not self.category_code.replace("-", "").replace("_", "").isalnum():
				frappe.throw("Category code should contain only letters, numbers, hyphens, and underscores")

	def validate_parent_category(self):
		"""Validate parent category selection"""
		if self.parent_category:
			# Check if parent is a group
			parent_doc = frappe.get_doc("Book Category", self.parent_category)
			if not parent_doc.is_group:
				frappe.throw("Parent category must be a group category")

			# Prevent circular reference
			if self.parent_category == self.name:
				frappe.throw("Category cannot be its own parent")

	def on_update(self):
		NestedSet.on_update(self)
		self.validate_name_change()

	def validate_name_change(self):
		"""Additional validations on name change"""
		if not self.is_new():
			# Check if this category has books assigned
			books_count = frappe.db.count('Book', {'category': self.name})
			if books_count > 0 and self.disabled:
				frappe.throw(f"Cannot disable category. {books_count} books are assigned to this category")

	def get_books_count(self, include_children=False):
		"""Get total number of books in this category"""
		if include_children and self.is_group:
			# Get all descendant categories
			descendants = frappe.db.sql("""
				SELECT name FROM `tabBook Category`
				WHERE lft >= %s AND rgt <= %s
				AND name != %s
			""", [self.lft, self.rgt, self.name], as_dict=True)

			category_list = [self.name] + [d.name for d in descendants]
			return frappe.db.count('Book', {'category': ['in', category_list]})
		else:
			return frappe.db.count('Book', {'category': self.name})

	@frappe.whitelist()
	def get_category_stats(self):
		"""Get comprehensive category statistics"""
		stats = {
			'direct_books': self.get_books_count(include_children=False),
			'total_books': self.get_books_count(include_children=True)
		}

		# Get most popular books in this category
		popular_books = frappe.db.sql("""
			SELECT b.name, b.title, b.author, COUNT(t.name) as issue_count
			FROM `tabBook` b
			LEFT JOIN `tabLibrary Transaction` t ON b.name = t.book
			WHERE b.category = %s
			GROUP BY b.name
			ORDER BY issue_count DESC
			LIMIT 10
		""", [self.name], as_dict=True)

		stats['popular_books'] = popular_books

		return stats

def get_category_tree():
	"""Get category tree structure"""
	categories = frappe.db.sql("""
		SELECT name, category_name, parent_category, is_group, lft, rgt
		FROM `tabBook Category`
		WHERE disabled = 0
		ORDER BY lft
	""", as_dict=True)

	return categories