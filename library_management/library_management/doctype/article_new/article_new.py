# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import flt
import pymysql

class Article_New(Document):
	def validate(self):
		self.validate_isbn()
		# Only update copy counts if this is not a new document
		# For new documents, counts will be updated after book creation
		if not self.is_new():
			self.update_copy_counts()

	def after_insert(self):
		"""Create book copies after article is saved"""
		# Use enqueue to avoid modification timestamp conflicts
		frappe.enqueue(
			'library_management.library_management.doctype.article_new.article_new.create_book_copies_async',
			article_name=self.name,
			copies_to_create=self.copies_to_create,
			title=self.title,
			queue='default',
			timeout=300
		)

	def on_update(self):
		"""Handle updates to copy count"""
		if self.has_value_changed('copies_to_create'):
			# Use enqueue to avoid modification timestamp conflicts
			frappe.enqueue(
				'library_management.library_management.doctype.article_new.article_new.manage_book_copies_async',
				article_name=self.name,
				required_copies=self.copies_to_create,
				queue='default',
				timeout=300
			)

	def create_book_copies(self):
		"""Create initial book copies for the article"""
		if not self.copies_to_create or self.copies_to_create <= 0:
			return

		created_copies = 0
		for copy_num in range(1, self.copies_to_create + 1):
			try:
				book_doc = frappe.new_doc('Book')
				book_doc.article = self.name
				book_doc.copy_number = copy_num
				book_doc.status = 'Available'
				book_doc.condition = 'Good'
				book_doc.acquisition_date = frappe.utils.today()

				# Generate barcode if not exists
				if not book_doc.barcode:
					book_doc.barcode = f"{self.name}-{copy_num:03d}"

				book_doc.save(ignore_permissions=True)
				created_copies += 1
			except Exception as e:
				frappe.log_error(f"Error creating book copy {copy_num}: {str(e)}")

		if created_copies > 0:
			frappe.msgprint(f"Created {created_copies} book copies for '{self.title}'")
			# Update counts after creating copies (without saving)
			self.update_copy_counts()

	def manage_book_copies(self):
		"""Manage book copies when copies_to_create changes"""
		current_copies = frappe.db.count('Book', {'article': self.name})
		required_copies = self.copies_to_create or 0

		if required_copies > current_copies:
			# Create additional copies
			for copy_num in range(current_copies + 1, required_copies + 1):
				try:
					book_doc = frappe.new_doc('Book')
					book_doc.article = self.name
					book_doc.copy_number = copy_num
					book_doc.status = 'Available'
					book_doc.condition = 'Good'
					book_doc.barcode = f"{self.name}-{copy_num:03d}"
					book_doc.save(ignore_permissions=True)
				except Exception as e:
					frappe.log_error(f"Error creating additional copy {copy_num}: {str(e)}")

			frappe.msgprint(f"Added {required_copies - current_copies} more copies")
		elif required_copies < current_copies:
			# Remove excess copies (only if they're available)
			excess_books = frappe.get_all('Book',
				filters={
					'article': self.name,
					'status': 'Available'
				},
				fields=['name'],
				order_by='copy_number desc',
				limit=(current_copies - required_copies)
			)

			for book in excess_books:
				try:
					frappe.delete_doc('Book', book.name, ignore_permissions=True)
				except Exception as e:
					frappe.log_error(f"Error removing excess copy {book.name}: {str(e)}")

			if excess_books:
				frappe.msgprint(f"Removed {len(excess_books)} excess available copies")

		# Update counts (without saving)
		self.update_copy_counts()

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

	def update_copy_counts(self):
		"""Update total and available copy counts from linked books"""
		try:
			# Get all books linked to this article
			books = frappe.get_all('Book',
				filters={'article': self.name},
				fields=['name', 'status'])

			self.total_copies = len(books)

			# Count available and issued books
			available_count = 0
			issued_count = 0
			for book in books:
				if book.status == 'Available':
					available_count += 1
				elif book.status == 'Issued':
					issued_count += 1

			self.available_copies = available_count
			self.issued_copies = issued_count

		except (pymysql.err.OperationalError, Exception) as e:
			# Handle case where article field doesn't exist yet in Book doctype
			if "Unknown column 'article'" in str(e):
				frappe.log_error(f"Article field not found in Book: {str(e)}")
			self.total_copies = 0
			self.available_copies = 0
			self.issued_copies = 0

	def get_available_books(self):
		"""Get list of available books for this article"""
		try:
			return frappe.get_all('Book',
				filters={
					'article': self.name,
					'status': 'Available'
				},
				fields=['name', 'barcode', 'condition', 'location']
			)
		except (pymysql.err.OperationalError, Exception) as e:
			if "Unknown column 'article'" in str(e):
				frappe.log_error(f"Article field not found in Book: {str(e)}")
			return []

	def get_issued_count(self):
		"""Get number of currently issued books for this article"""
		try:
			issued_count = frappe.db.count('Library Transaction', {
				'article': self.name,
				'status': 'Issued',
				'docstatus': 1
			})
			return issued_count or 0
		except (pymysql.err.OperationalError, Exception) as e:
			if "Unknown column 'article'" in str(e):
				frappe.log_error(f"Article field not found in Library Transaction: {str(e)}")
			return 0

	def get_average_rating(self):
		"""Get average rating from book reviews"""
		try:
			avg_rating = frappe.db.sql("""
				SELECT AVG(rating)
				FROM `tabBook Review`
				WHERE article = %s AND status = 'Approved' AND docstatus = 1
			""", [self.name])

			return flt(avg_rating[0][0]) if avg_rating and avg_rating[0][0] else 0
		except (pymysql.err.OperationalError, Exception) as e:
			if "Unknown column 'article'" in str(e):
				frappe.log_error(f"Article field not found in Book Review: {str(e)}")
			return 0

	def get_total_reviews(self):
		"""Get total number of approved reviews"""
		try:
			return frappe.db.count('Book Review', {
				'article': self.name,
				'status': 'Approved',
				'docstatus': 1
			})
		except (pymysql.err.OperationalError, Exception) as e:
			if "Unknown column 'article'" in str(e):
				frappe.log_error(f"Article field not found in Book Review: {str(e)}")
			return 0

	def is_available_for_issue(self):
		"""Check if article has available copies for issue"""
		return self.status == "Active" and self.available_copies > 0

	@frappe.whitelist()
	def refresh_copy_counts(self):
		"""Manually refresh copy counts from linked books"""
		self.update_copy_counts()
		self.save(ignore_permissions=True)
		frappe.msgprint(f"Updated: {self.total_copies} total, {self.available_copies} available")

	@frappe.whitelist()
	def create_copies_now(self):
		"""Manual method to create book copies immediately"""
		if not self.copies_to_create or self.copies_to_create <= 0:
			frappe.throw("Please specify number of copies to create")

		current_copies = frappe.db.count('Book', {'article': self.name})
		if current_copies >= self.copies_to_create:
			frappe.msgprint(f"Already have {current_copies} copies. No additional copies needed.")
			return

		# Create the copies immediately
		created_copies = 0
		for copy_num in range(current_copies + 1, self.copies_to_create + 1):
			try:
				book_doc = frappe.new_doc('Book')
				book_doc.article = self.name
				book_doc.copy_number = copy_num
				book_doc.status = 'Available'
				book_doc.condition = 'Good'
				book_doc.acquisition_date = frappe.utils.today()
				book_doc.barcode = f"{self.name}-{copy_num:03d}"
				book_doc.save(ignore_permissions=True)
				created_copies += 1
			except Exception as e:
				frappe.log_error(f"Error creating book copy {copy_num}: {str(e)}")
				frappe.throw(f"Error creating copy {copy_num}: {str(e)}")

		if created_copies > 0:
			# Update counts
			self.update_copy_counts()
			self.save(ignore_permissions=True)
			frappe.msgprint(f"Successfully created {created_copies} book copies!")
		else:
			frappe.throw("No copies were created due to errors")

def get_articles_by_category(category):
	"""Get all articles in a specific category"""
	return frappe.get_all('Article_New',
		filters={'category': category, 'status': 'Active'},
		fields=['name', 'title', 'primary_author', 'available_copies']
	)

def get_popular_articles(limit=10):
	"""Get most popular articles based on issue count"""
	popular_articles = frappe.db.sql("""
		SELECT a.name, a.title, a.primary_author, COUNT(t.name) as issue_count
		FROM `tabArticle_New` a
		LEFT JOIN `tabLibrary Transaction` t ON a.name = t.article
		WHERE a.status = 'Active'
		GROUP BY a.name
		ORDER BY issue_count DESC
		LIMIT %s
	""", [limit], as_dict=True)

	return popular_articles

# Async functions to avoid timestamp conflicts
def create_book_copies_async(article_name, copies_to_create, title):
	"""Create book copies asynchronously"""
	if not copies_to_create or copies_to_create <= 0:
		return

	created_copies = 0
	for copy_num in range(1, copies_to_create + 1):
		try:
			book_doc = frappe.new_doc('Book')
			book_doc.article = article_name
			book_doc.copy_number = copy_num
			book_doc.status = 'Available'
			book_doc.condition = 'Good'
			book_doc.acquisition_date = frappe.utils.today()

			# Generate barcode
			book_doc.barcode = f"{article_name}-{copy_num:03d}"

			book_doc.save(ignore_permissions=True)
			created_copies += 1
		except Exception as e:
			frappe.log_error(f"Error creating book copy {copy_num} for {article_name}: {str(e)}")

	if created_copies > 0:
		# Update article counts
		try:
			article_doc = frappe.get_doc('Article_New', article_name)
			article_doc.update_copy_counts()
			article_doc.save(ignore_permissions=True)
			frappe.publish_realtime('msgprint', f"Created {created_copies} book copies for '{title}'")
		except Exception as e:
			frappe.log_error(f"Error updating article counts for {article_name}: {str(e)}")

	frappe.db.commit()

def manage_book_copies_async(article_name, required_copies):
	"""Manage book copies asynchronously"""
	current_copies = frappe.db.count('Book', {'article': article_name})
	required_copies = required_copies or 0

	if required_copies > current_copies:
		# Create additional copies
		created_copies = 0
		for copy_num in range(current_copies + 1, required_copies + 1):
			try:
				book_doc = frappe.new_doc('Book')
				book_doc.article = article_name
				book_doc.copy_number = copy_num
				book_doc.status = 'Available'
				book_doc.condition = 'Good'
				book_doc.barcode = f"{article_name}-{copy_num:03d}"
				book_doc.save(ignore_permissions=True)
				created_copies += 1
			except Exception as e:
				frappe.log_error(f"Error creating additional copy {copy_num} for {article_name}: {str(e)}")

		if created_copies > 0:
			frappe.publish_realtime('msgprint', f"Added {created_copies} more copies")

	elif required_copies < current_copies:
		# Remove excess copies (only if they're available)
		excess_books = frappe.get_all('Book',
			filters={
				'article': article_name,
				'status': 'Available'
			},
			fields=['name'],
			order_by='copy_number desc',
			limit=(current_copies - required_copies)
		)

		removed_copies = 0
		for book in excess_books:
			try:
				frappe.delete_doc('Book', book.name, ignore_permissions=True)
				removed_copies += 1
			except Exception as e:
				frappe.log_error(f"Error removing excess copy {book.name}: {str(e)}")

		if removed_copies > 0:
			frappe.publish_realtime('msgprint', f"Removed {removed_copies} excess available copies")

	# Update article counts
	try:
		article_doc = frappe.get_doc('Article_New', article_name)
		article_doc.update_copy_counts()
		article_doc.save(ignore_permissions=True)
	except Exception as e:
		frappe.log_error(f"Error updating article counts for {article_name}: {str(e)}")

	frappe.db.commit()
