# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import add_days, getdate, now_datetime
import pymysql

class LibraryTransaction(Document):

	def validate(self):
		self.validate_article_and_book()
		self.validate_transaction_type()
		self.validate_member_eligibility()
		self.validate_book_availability()
		self.validate_return_eligibility()
		self.set_due_date()

	def validate_article_and_book(self):
		"""Ensure article and book are properly linked"""
		if not self.article or not self.book:
			frappe.throw("Both Article and Book Copy must be specified")

		# Validate that book belongs to the article
		book_article = frappe.db.get_value('Book', self.book, 'article')
		if book_article != self.article:
			frappe.throw(f"Selected book copy does not belong to the specified article")

	def validate_transaction_type(self):
		"""Validate transaction type based on context"""
		# This method now focuses on basic transaction type validation
		# Return eligibility validation is handled in validate_return_eligibility()
		pass

	def validate_member_eligibility(self):
		"""Check if member is eligible for transactions"""
		member_doc = frappe.get_doc('Library Member', self.library_member)

		# Check if member is active
		if getattr(member_doc, 'status', '') == 'Inactive':
			frappe.throw("Member is inactive and cannot perform transactions")

		# Check for outstanding fines (if applicable)
		outstanding_fines = frappe.db.sql("""
			SELECT SUM(fine_amount)
			FROM `tabLibrary Transaction`
			WHERE library_member = %s AND fine_amount > 0 AND docstatus = 1
		""", [self.library_member])

		if outstanding_fines[0][0] and outstanding_fines[0][0] > 0:
			frappe.msgprint(f"Member has outstanding fines of {outstanding_fines[0][0]}")

	def validate_book_availability(self):
		"""Validate book is available for issue"""
		if self.transaction_type == "Issue":
			book_status = frappe.db.get_value('Book', self.book, 'status')
			if book_status == 'Reserved':
				# Check if this book is reserved for this member
				reservation_exists = frappe.db.exists('Book Reservation', {
					'selected_book': self.book,
					'member': self.library_member,
					'status': 'Active',
					'docstatus': 1
				})

				if not reservation_exists:
					frappe.throw(f"Book is reserved for another member. Cannot issue until reservation is cancelled or fulfilled.")
			elif book_status != 'Available':
				frappe.throw(f"Book is not available for issue. Current status: {book_status}")

	def debug_existing_transactions(self, book=None, member=None):
		"""Debug method to show existing transactions for troubleshooting"""
		book = book or self.book
		member = member or self.library_member

		if not book or not member:
			return "Missing book or member information"

		# Get all transactions for this book and member
		all_transactions = frappe.get_all('Library Transaction',
			filters={
				'book': book,
				'library_member': member
			},
			fields=['name', 'transaction_type', 'status', 'docstatus', 'date', 'creation'],
			order_by='creation desc'
		)

		# Get detailed info for debugging
		debug_info = {
			'book': book,
			'member': member,
			'total_transactions': len(all_transactions),
			'transactions': all_transactions
		}

		# Count by status and type
		issued_count = len([t for t in all_transactions if t.status == 'Issued' and t.docstatus == 1])
		draft_count = len([t for t in all_transactions if t.docstatus == 0])

		debug_info['summary'] = {
			'issued_and_submitted': issued_count,
			'draft_transactions': draft_count
		}

		return debug_info

	def validate_return_eligibility(self):
		"""Validate return transaction eligibility"""
		if self.transaction_type == "Return":
			# Build filter conditions properly
			filters = {
				'book': self.book,
				'library_member': self.library_member,
				'transaction_type': 'Issue',
				'status': 'Issued',
				'docstatus': 1
			}

			# Exclude current transaction if it's not new
			if not self.is_new() and self.name:
				filters['name'] = ['!=', self.name]

			# Check if there's an active issue for this specific book and member
			active_issue = frappe.db.exists('Library Transaction', filters)

			if not active_issue:
				# Get debugging information
				debug_info = self.debug_existing_transactions()

				# Create detailed error message
				error_msg = f"No active issue found for book {self.book} by member {self.library_member}.\n\n"
				error_msg += f"Validation Criteria:\n"
				error_msg += f"- Book: {self.book}\n"
				error_msg += f"- Member: {self.library_member}\n"
				error_msg += f"- Transaction Type: Issue\n"
				error_msg += f"- Status: Issued\n"
				error_msg += f"- Document Status: Submitted (1)\n\n"

				error_msg += f"Debug Information:\n"
				error_msg += f"- Total transactions found: {debug_info['total_transactions']}\n"
				error_msg += f"- Issued & submitted: {debug_info['summary']['issued_and_submitted']}\n"
				error_msg += f"- Draft transactions: {debug_info['summary']['draft_transactions']}\n\n"

				if debug_info['transactions']:
					error_msg += "Existing transactions:\n"
					for t in debug_info['transactions'][:5]:  # Show first 5
						error_msg += f"- {t.name}: {t.transaction_type}, Status: {t.status}, DocStatus: {t.docstatus}\n"

				frappe.throw(error_msg)

	def set_due_date(self):
		"""Set due date for issue transactions"""
		if self.transaction_type == "Issue" and not self.due_date:
			# Default loan period of 14 days
			loan_period = frappe.db.get_single_value('Library Settings', 'loan_period') or 14
			self.due_date = add_days(getdate(self.date), loan_period)

	def before_submit(self):
		"""Update status before submit"""
		if self.transaction_type == "Issue":
			self.status = "Issued"
		elif self.transaction_type == "Return":
			self.status = "Returned"
			self.return_date = now_datetime()
			self.check_overdue()

	def on_submit(self):
		"""Update related documents on submit"""
		self.update_book_status()
		self.update_article_counts()
		self.create_member_history()
		self.update_book_last_issue_date()

	def update_book_status(self):
		"""Update book status based on transaction"""
		try:
			book_doc = frappe.get_doc('Book', self.book)

			if self.transaction_type == "Issue":
				book_doc.status = "Issued"
				book_doc.last_issue_date = self.date
			elif self.transaction_type == "Return":
				book_doc.status = "Available"
				# Check for pending reservations when book becomes available
				self.check_pending_reservations()

			book_doc.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Error updating book status: {str(e)}")

	def check_pending_reservations(self):
		"""Check for pending reservations when a book becomes available"""
		try:
			# Import here to avoid circular imports
			from library_management.library_management.doctype.book_reservation.book_reservation import check_article_availability_for_reservations

			# Notify waiting reservations for this article
			check_article_availability_for_reservations(self.article)
		except Exception as e:
			frappe.log_error(f"Error checking pending reservations: {str(e)}")

	def update_article_counts(self):
		"""Update parent article's copy counts"""
		try:
			article_doc = frappe.get_doc('Article_New', self.article)
			article_doc.update_copy_counts()
			article_doc.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Error updating article counts: {str(e)}")

	def create_member_history(self):
		"""Create or update member history record"""
		try:
			# Check if history record exists
			history_name = frappe.db.get_value('Library Member History',
				{'member_name': self.library_member}, 'name')

			if history_name:
				history_doc = frappe.get_doc('Library Member History', history_name)
			else:
				history_doc = frappe.new_doc('Library Member History')
				history_doc.member_name = self.library_member

			# Get article and book details
			article_title = frappe.db.get_value('Article_New', self.article, 'title')
			copy_number = frappe.db.get_value('Book', self.book, 'copy_number')

			# Determine status
			transaction_status = "Active"
			if self.transaction_type == "Return":
				transaction_status = "Completed"
			elif getattr(self, 'is_overdue', False):
				transaction_status = "Overdue"

			# Add transaction to history
			history_doc.append("transaction_history", {
				"transaction_type": self.transaction_type,
				"article": self.article,
				"article_title": article_title,
				"book": self.book,
				"copy_number": copy_number,
				"transaction_date": self.date,
				"due_date": self.due_date if self.transaction_type == "Issue" else None,
				"return_date": self.return_date if self.transaction_type == "Return" else None,
				"status": transaction_status,
				"fine_amount": self.fine_amount or 0
			})

			history_doc.save(ignore_permissions=True)

			# If this is a return transaction, update the corresponding issue entry status
			if self.transaction_type == "Return":
				self.update_issue_history_status(history_doc)

		except Exception as e:
			frappe.log_error(f"Error creating member history: {str(e)}")

	def update_issue_history_status(self, history_doc):
		"""Update the status of the corresponding issue entry"""
		try:
			# Find the corresponding issue entry
			for row in history_doc.transaction_history:
				if (row.transaction_type == "Issue" and
					row.book == self.book and
					row.status == "Active"):
					row.status = "Completed"
					row.return_date = self.return_date or self.date
					if self.fine_amount:
						row.fine_amount = self.fine_amount
					break

			history_doc.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Error updating issue history status: {str(e)}")

	def update_book_last_issue_date(self):
		"""Update book's last issue date"""
		if self.transaction_type == "Issue":
			try:
				frappe.db.set_value('Book', self.book, 'last_issue_date', self.date)
			except Exception as e:
				frappe.log_error(f"Error updating book last issue date: {str(e)}")

	def check_overdue(self):
		"""Check if return is overdue and calculate fine"""
		if self.transaction_type == "Return" and self.due_date:
			return_date = getdate(self.return_date or self.date)
			due_date = getdate(self.due_date)

			if return_date > due_date:
				self.is_overdue = 1
				overdue_days = (return_date - due_date).days

				# Calculate fine (configurable rate)
				fine_per_day = frappe.db.get_single_value('Library Settings', 'fine_per_day') or 1.0
				self.fine_amount = overdue_days * fine_per_day

				frappe.msgprint(f"Book returned {overdue_days} days late. Fine: {self.fine_amount}")

	@frappe.whitelist()
	def get_available_books(self):
		"""Get available books for selected article"""
		if not self.article:
			return []

		return frappe.get_all('Book',
			filters={
				'article': self.article,
				'status': 'Available'
			},
			fields=['name', 'copy_number', 'barcode', 'location', 'condition']
		)

# Utility functions
def get_member_issued_books(member):
	"""Get all currently issued books for a member"""
	return frappe.get_all('Library Transaction',
		filters={
			'library_member': member,
			'status': 'Issued',
			'docstatus': 1
		},
		fields=['name', 'article', 'book', 'date', 'due_date']
	)

def get_overdue_books(member=None):
	"""Get all overdue books, optionally filtered by member"""
	filters = {
		'status': 'Issued',
		'due_date': ['<', getdate()],
		'docstatus': 1
	}

	if member:
		filters['library_member'] = member

	return frappe.get_all('Library Transaction',
		filters=filters,
		fields=['name', 'library_member', 'article', 'book', 'date', 'due_date']
	)

@frappe.whitelist()
def get_available_books_for_member(article, member):
	"""Get available books and member's reserved books for the selected article"""
	# Get available books
	available_books = frappe.get_all('Book',
		filters={
			'article': article,
			'status': 'Available'
		},
		fields=['name', 'copy_number', 'barcode', 'location', 'condition', 'status']
	)

	# Get books reserved for this member
	reserved_books = frappe.db.sql("""
		SELECT b.name, b.copy_number, b.barcode, b.location, b.`condition`, b.status
		FROM `tabBook` b
		INNER JOIN `tabBook Reservation` br ON b.name = br.selected_book
		WHERE b.article = %s
		AND b.status = 'Reserved'
		AND br.member = %s
		AND br.status = 'Active'
		AND br.docstatus = 1
	""", [article, member], as_dict=True)

	# Combine both lists
	all_books = available_books + reserved_books
	return all_books

@frappe.whitelist()
def create_return_transaction(issue_transaction):
	"""Create return transaction from issue transaction"""
	issue_doc = frappe.get_doc('Library Transaction', issue_transaction)

	# Validate that the issue transaction is actually issued
	if issue_doc.transaction_type != 'Issue' or issue_doc.status != 'Issued':
		frappe.throw(f"Cannot create return for transaction {issue_transaction}. Transaction type: {issue_doc.transaction_type}, Status: {issue_doc.status}")

	# Check if return already exists
	existing_return = frappe.db.exists('Library Transaction', {
		'book': issue_doc.book,
		'library_member': issue_doc.library_member,
		'transaction_type': 'Return',
		'docstatus': ['!=', 2]  # Not cancelled
	})

	if existing_return:
		frappe.throw(f"Return transaction already exists for this book and member: {existing_return}")

	return_doc = frappe.new_doc('Library Transaction')
	return_doc.article = issue_doc.article
	return_doc.book = issue_doc.book
	return_doc.library_member = issue_doc.library_member
	return_doc.transaction_type = "Return"
	return_doc.date = now_datetime()
	return_doc.due_date = issue_doc.due_date

	# Save the return transaction
	return_doc.save(ignore_permissions=True)

	frappe.msgprint(f"Return transaction {return_doc.name} created for book {return_doc.book}")

	return return_doc

@frappe.whitelist()
def get_book_query(doctype, txt, searchfield, start, page_len, filters):
	"""Filter books based on selected article and transaction type"""
	if not filters:
		filters = {}

	# Get context from filters or from the current form
	article = filters.get('article')
	transaction_type = filters.get('transaction_type')
	library_member = filters.get('library_member')

	if not article:
		# If no article selected, return all books
		return frappe.db.sql("""
			SELECT name, copy_number, barcode, status
			FROM `tabBook`
			WHERE name LIKE %(txt)s OR barcode LIKE %(txt)s
			ORDER BY copy_number
			LIMIT %(start)s, %(page_len)s
		""", {
			'txt': f"%{txt}%",
			'start': start,
			'page_len': page_len
		})

	# Build dynamic query conditions
	conditions = ["article = %(article)s"]
	query_params = {
		'txt': f"%{txt}%",
		'article': article,
		'start': start,
		'page_len': page_len
	}

	if transaction_type == 'Issue':
		# For issue transactions, show available books and reserved books for this member
		if library_member:
			conditions.append("""
				(status = 'Available' OR
				 (status = 'Reserved' AND name IN (
					SELECT selected_book FROM `tabBook Reservation`
					WHERE member = %(library_member)s
					AND status = 'Active'
					AND docstatus = 1
					AND selected_book IS NOT NULL
				 )))
			""")
		else:
			conditions.append("status = 'Available'")
	elif transaction_type == 'Return' and library_member:
		# For return transactions, only show books issued to this member
		conditions.append("""
			status = 'Issued' AND name IN (
				SELECT book FROM `tabLibrary Transaction`
				WHERE library_member = %(library_member)s
				AND status = 'Issued'
				AND docstatus = 1
			)
		""")
		query_params['library_member'] = library_member

	where_clause = " AND ".join(conditions)

	return frappe.db.sql(f"""
		SELECT name, copy_number, barcode, status, `condition`
		FROM `tabBook`
		WHERE {where_clause}
		AND (name LIKE %(txt)s OR barcode LIKE %(txt)s)
		ORDER BY copy_number
		LIMIT %(start)s, %(page_len)s
	""", query_params)

@frappe.whitelist()
def get_member_issued_books_with_details(member):
	"""Get all currently issued books for a member with detailed information"""
	if not member:
		return []

	# Get all issued transactions for the member with article and book details
	issued_books = frappe.db.sql("""
		SELECT
			lt.name as transaction_name,
			lt.article,
			lt.book,
			lt.date as issue_date,
			lt.due_date,
			DATEDIFF(CURDATE(), lt.due_date) as days_overdue,
			a.title as article_title,
			a.author,
			a.isbn,
			b.copy_number,
			b.barcode,
			b.location,
			b.condition as book_condition
		FROM `tabLibrary Transaction` lt
		INNER JOIN `tabArticle_New` a ON lt.article = a.name
		INNER JOIN `tabBook` b ON lt.book = b.name
		WHERE lt.library_member = %s
		AND lt.transaction_type = 'Issue'
		AND lt.status = 'Issued'
		AND lt.docstatus = 1
		ORDER BY lt.due_date ASC
	""", [member], as_dict=True)

	# Add overdue flag to each book
	for book in issued_books:
		book['is_overdue'] = book['days_overdue'] > 0 if book['days_overdue'] else False

	return issued_books

@frappe.whitelist()
def debug_transaction_issues(book, member):
	"""Debug utility to check transaction issues for a specific book and member"""
	if not book or not member:
		return {"error": "Both book and member are required"}

	# Get all transactions
	all_transactions = frappe.get_all('Library Transaction',
		filters={
			'book': book,
			'library_member': member
		},
		fields=['name', 'transaction_type', 'status', 'docstatus', 'date', 'creation'],
		order_by='creation desc'
	)

	# Find active issues
	active_issues = frappe.get_all('Library Transaction',
		filters={
			'book': book,
			'library_member': member,
			'transaction_type': 'Issue',
			'status': 'Issued',
			'docstatus': 1
		},
		fields=['name', 'status', 'docstatus', 'date']
	)

	# Check book status
	book_status = frappe.db.get_value('Book', book, 'status')

	return {
		'book': book,
		'member': member,
		'book_status': book_status,
		'total_transactions': len(all_transactions),
		'active_issues': len(active_issues),
		'all_transactions': all_transactions,
		'active_issue_details': active_issues
	}