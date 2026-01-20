# Copyright (c) 2023, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
import pymysql

class Book(Document):
	def validate(self):
		self.validate_copy_number()
		self.validate_barcode()
		self.update_article_counts()

	def validate_copy_number(self):
		"""Validate copy number is unique within the article"""
		if self.copy_number and self.article:
			existing = frappe.db.exists('Book', {
				'article': self.article,
				'copy_number': self.copy_number,
				'name': ['!=', self.name]
			})
			if existing:
				frappe.throw(f"Copy number {self.copy_number} already exists for this article")

	def validate_barcode(self):
		"""Validate barcode is unique if provided"""
		if self.barcode:
			existing = frappe.db.exists('Book', {
				'barcode': self.barcode,
				'name': ['!=', self.name]
			})
			if existing:
				frappe.throw(f"Barcode {self.barcode} already exists")

	def update_article_counts(self):
		"""Update parent article's copy counts"""
		if self.article:
			try:
				article_doc = frappe.get_doc('Article_New', self.article)
				article_doc.update_copy_counts()
				article_doc.save(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(f"Error updating article counts: {str(e)}")

	def on_update(self):
		"""Update article copy counts when book is updated"""
		self.update_article_counts()

	def on_trash(self):
		"""Update article copy counts when book is deleted"""
		if self.article:
			try:
				article_doc = frappe.get_doc('Article_New', self.article)
				article_doc.update_copy_counts()
				article_doc.save(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(f"Error updating article counts on deletion: {str(e)}")

	def is_available_for_issue(self):
		"""Check if this specific book copy is available for issue"""
		return self.status == "Available" and self.condition not in ["Damaged", "Poor"]

	def get_issue_history(self, limit=10):
		"""Get issue history for this specific book copy"""
		try:
			return frappe.get_all('Library Transaction',
				filters={'book': self.name},
				fields=['name', 'library_member', 'date', 'status', 'returned'],
				order_by='date desc',
				limit=limit
			)
		except Exception as e:
			frappe.log_error(f"Error getting issue history: {str(e)}")
			return []

	def get_current_issuer(self):
		"""Get current member who has issued this book"""
		if self.status == "Issued":
			try:
				transaction = frappe.db.get_value('Library Transaction', {
					'book': self.name,
					'status': 'Issued',
					'returned': 0
				}, ['library_member', 'date'])
				return transaction
			except Exception as e:
				frappe.log_error(f"Error getting current issuer: {str(e)}")
		return None

	@frappe.whitelist()
	def mark_for_maintenance(self, reason=None):
		"""Mark book for maintenance"""
		if self.status == "Issued":
			frappe.throw("Cannot mark issued book for maintenance")

		self.status = "Maintenance"
		if reason:
			if self.maintenance_log:
				self.maintenance_log += f"\n{frappe.utils.now()}: {reason}"
			else:
				self.maintenance_log = f"{frappe.utils.now()}: {reason}"
		self.save()
		frappe.msgprint(f"Book {self.name} marked for maintenance")

	@frappe.whitelist()
	def mark_available(self):
		"""Mark book as available after maintenance"""
		if self.status == "Maintenance":
			self.status = "Available"
			if self.maintenance_log:
				self.maintenance_log += f"\n{frappe.utils.now()}: Returned to service"
			self.save()
			frappe.msgprint(f"Book {self.name} marked as available")


def get_books_by_article(article, status=None):
	"""Get all book copies for a specific article"""
	filters = {'article': article}
	if status:
		filters['status'] = status

	return frappe.get_all('Book',
		filters=filters,
		fields=['name', 'copy_number', 'barcode', 'status', 'condition', 'location'],
		order_by='copy_number'
	)

def get_available_books_for_article(article):
	"""Get available book copies for a specific article"""
	return get_books_by_article(article, 'Available')

def get_next_copy_number(article):
	"""Get the next available copy number for an article"""
	max_copy = frappe.db.sql("""
		SELECT MAX(copy_number)
		FROM `tabBook`
		WHERE article = %s
	""", [article])

	return (max_copy[0][0] or 0) + 1 if max_copy else 1