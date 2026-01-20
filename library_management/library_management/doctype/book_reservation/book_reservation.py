# Copyright (c) 2023, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, add_days, getdate

class BookReservation(Document):
	def validate(self):
		self.validate_member_eligibility()
		self.validate_duplicate_reservation()
		self.validate_selected_book()
		self.set_priority_level()
		self.set_expiry_date()
		self.update_available_books_list()

	def validate_selected_book(self):
		"""Validate selected book belongs to article and is available"""
		if self.selected_book:
			book_doc = frappe.get_doc('Book', self.selected_book)
			if book_doc.article != self.article:
				frappe.throw("Selected book does not belong to this article")
			if book_doc.status != 'Available':
				frappe.throw(f"Selected book is not available. Current status: {book_doc.status}")

	def update_available_books_list(self):
		"""Update the HTML field with available books"""
		if not self.article:
			self.available_books_list = ""
			return

		available_books = frappe.get_all('Book',
			filters={
				'article': self.article,
				'status': 'Available'
			},
			fields=['name', 'copy_number', 'barcode', 'condition', 'location'],
			order_by='copy_number'
		)

		if not available_books:
			self.available_books_list = "<p><em>No copies available for reservation</em></p>"
			return

		html_content = "<div class='available-books-list'>"
		html_content += "<h5>Available Copies:</h5>"
		html_content += "<table class='table table-bordered table-condensed'>"
		html_content += "<thead><tr><th>Copy #</th><th>Barcode</th><th>Condition</th><th>Location</th><th>Action</th></tr></thead>"
		html_content += "<tbody>"

		for book in available_books:
			html_content += f"<tr>"
			html_content += f"<td>{book.copy_number}</td>"
			html_content += f"<td>{book.barcode or '-'}</td>"
			html_content += f"<td>{book.condition}</td>"
			html_content += f"<td>{book.location or '-'}</td>"
			html_content += f"<td><button type='button' class='btn btn-xs btn-primary' onclick='selectBook(\"{book.name}\")'>"
			html_content += f"Select</button></td>"
			html_content += f"</tr>"

		html_content += "</tbody></table></div>"
		html_content += """<script>
			function selectBook(bookName) {
				cur_frm.set_value('selected_book', bookName);
				frappe.msgprint('Book copy selected: ' + bookName);
			}
		</script>"""

		self.available_books_list = html_content

	def validate_member_eligibility(self):
		"""Validate member can make reservations"""
		member = frappe.get_doc("Library Member", self.member)

		# Check if member is active
		if getattr(member, 'disabled', False):
			frappe.throw("Cannot create reservation for inactive member")

		# Check if member already has this article issued
		existing_issue = frappe.db.exists('Library Transaction', {
			'library_member': self.member,
			'article': self.article,
			'transaction_type': 'Issue',
			'status': 'Issued',
			'docstatus': 1
		})

		if existing_issue:
			# Get debugging information
			all_transactions = frappe.get_all('Library Transaction',
				filters={
					'library_member': self.member,
					'article': self.article
				},
				fields=['name', 'transaction_type', 'status', 'docstatus', 'date'],
				order_by='creation desc'
			)

			error_msg = f"You already have this article issued.\n\n"
			error_msg += f"Active Issue Transaction: {existing_issue}\n\n"

			if all_transactions:
				error_msg += "Recent transactions for this article:\n"
				for t in all_transactions[:3]:
					error_msg += f"- {t.name}: {t.transaction_type}, Status: {t.status}, DocStatus: {t.docstatus}, Date: {t.date}\n"

			frappe.throw(error_msg)

		# Check for outstanding fines
		outstanding_fines = frappe.db.sql("""
			SELECT SUM(fine_amount)
			FROM `tabLibrary Transaction`
			WHERE library_member = %s AND fine_amount > 0 AND docstatus = 1
		""", [self.member])

		if outstanding_fines[0][0] and outstanding_fines[0][0] > 0:
			frappe.msgprint(f"Member has outstanding fines of {outstanding_fines[0][0]}")

	def validate_duplicate_reservation(self):
		"""Prevent duplicate active reservations"""
		if not self.is_new():
			return

		existing_reservation = frappe.db.exists('Book Reservation', {
			'article': self.article,
			'member': self.member,
			'status': 'Active',
			'name': ['!=', self.name]
		})

		if existing_reservation:
			frappe.throw("You already have an active reservation for this article")

	def set_priority_level(self):
		"""Set priority based on member type"""
		try:
			member = frappe.get_doc("Library Member", self.member)
			if getattr(member, 'member_type', None):
				member_type = frappe.get_doc("Member Type", member.member_type)
				self.priority_level = getattr(member_type, 'priority_level', 5)
			else:
				self.priority_level = 5  # Standard priority
		except Exception:
			self.priority_level = 5

	def set_expiry_date(self):
		"""Set reservation expiry date"""
		if not self.expiry_date:
			# Default 7 days from reservation date
			self.expiry_date = add_days(self.reservation_date, 7)

	def on_submit(self):
		"""Actions after submitting reservation"""
		self.check_article_availability()
		self.create_reservation_history()
		self.update_book_status_if_selected()

	def check_article_availability(self):
		"""Check if article has available copies"""
		article = frappe.get_doc("Article_New", self.article)

		if article.is_available_for_issue():
			# Article has available copies, notify member immediately
			self.send_availability_notification()
		else:
			# Article not available, add to queue
			queue_position = self.get_queue_position()
			if queue_position <= 1:
				frappe.msgprint(f"You are next in queue for '{self.article_title}'")

	def send_availability_notification(self):
		"""Send notification when article becomes available"""
		if self.notification_sent:
			return

		try:
			member = frappe.get_doc("Library Member", self.member)
			member_email = getattr(member, 'email_address', None) or getattr(member, 'email_id', None)

			if member_email:
				frappe.sendmail(
					recipients=[member_email],
					subject=f"Article Available for Pickup: {self.article_title}",
					message=f"""
					Dear {getattr(member, 'full_name', member.name)},

					The article "{self.article_title}" by {self.author} that you reserved is now available for pickup.

					Please visit the library within 3 days to collect a copy.
					After this period, the reservation will expire and the article will be available to the next person in queue.

					Best regards,
					Library Management System
					""",
					reference_doctype=self.doctype,
					reference_name=self.name
				)

				self.notification_sent = 1
				self.notified_date = today()
				self.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Error sending availability notification: {str(e)}")

	def get_queue_position(self):
		"""Get position in reservation queue"""
		reservations_ahead = frappe.db.count('Book Reservation', {
			'article': self.article,
			'status': 'Active',
			'reservation_date': ['<', self.reservation_date],
			'priority_level': ['>=', self.priority_level],
			'docstatus': 1
		})

		# Also count higher priority reservations made after this one
		higher_priority = frappe.db.count('Book Reservation', {
			'article': self.article,
			'status': 'Active',
			'priority_level': ['>', self.priority_level],
			'docstatus': 1
		})

		return reservations_ahead + higher_priority + 1

	def create_reservation_history(self):
		"""Create or update member history record for reservation"""
		try:
			# Check if history record exists
			history_name = frappe.db.get_value('Library Member History',
				{'member_name': self.member}, 'name')

			if history_name:
				history_doc = frappe.get_doc('Library Member History', history_name)
			else:
				history_doc = frappe.new_doc('Library Member History')
				history_doc.member_name = self.member

			# Get copy number if book is selected
			copy_number = None
			if self.selected_book:
				copy_number = frappe.db.get_value('Book', self.selected_book, 'copy_number')

			# Add reservation to history
			history_doc.append("transaction_history", {
				"transaction_type": "Reservation",
				"article": self.article,
				"article_title": self.article_title,
				"book": self.selected_book,
				"copy_number": copy_number,
				"transaction_date": self.reservation_date,
				"due_date": self.expiry_date,
				"return_date": None,
				"status": "Active",
				"fine_amount": 0
			})

			history_doc.save(ignore_permissions=True)

		except Exception as e:
			frappe.log_error(f"Error creating reservation history: {str(e)}")

	def update_book_status_if_selected(self):
		"""Update book status to Reserved if a specific book is selected"""
		if self.selected_book:
			try:
				book_doc = frappe.get_doc('Book', self.selected_book)
				book_doc.status = 'Reserved'
				book_doc.save(ignore_permissions=True)
				frappe.msgprint(f"Book {self.selected_book} has been marked as Reserved")
			except Exception as e:
				frappe.log_error(f"Error updating book status to Reserved: {str(e)}")

	@frappe.whitelist()
	def fulfill_reservation(self):
		"""Mark reservation as fulfilled when article is issued"""
		if self.status != "Active":
			frappe.throw("Can only fulfill active reservations")

		if not self.selected_book:
			frappe.throw("Please select a book copy before fulfilling the reservation")

		# Create library transaction for issue
		transaction = frappe.new_doc('Library Transaction')
		transaction.article = self.article
		transaction.book = self.selected_book
		transaction.library_member = self.member
		transaction.transaction_type = 'Issue'
		transaction.date = frappe.utils.now_datetime()
		transaction.save(ignore_permissions=True)
		transaction.submit()

		self.status = "Fulfilled"
		self.update_reservation_history_status()
		self.save()

		# Notify next person in queue
		self.notify_next_in_queue()

		frappe.msgprint(f"Reservation fulfilled. Book {self.selected_book} has been issued to {self.member}")

		return transaction.name

	@frappe.whitelist()
	def create_return_from_reservation(self):
		"""Create return transaction for a fulfilled reservation"""
		if self.status != "Fulfilled":
			frappe.throw("Can only create return for fulfilled reservations")

		if not self.selected_book:
			frappe.throw("No book selected for this reservation")

		# Check if there's an active issue for this book and member
		issue_transaction = frappe.db.get_value('Library Transaction', {
			'book': self.selected_book,
			'library_member': self.member,
			'transaction_type': 'Issue',
			'status': 'Issued',
			'docstatus': 1
		}, 'name')

		if not issue_transaction:
			# Get all transactions for debugging
			all_transactions = frappe.get_all('Library Transaction',
				filters={
					'book': self.selected_book,
					'library_member': self.member
				},
				fields=['name', 'transaction_type', 'status', 'docstatus'],
				order_by='creation desc'
			)

			error_msg = f"No active issue found for book {self.selected_book} by member {self.member}.\n\n"
			if all_transactions:
				error_msg += "Existing transactions:\n"
				for t in all_transactions[:3]:
					error_msg += f"- {t.name}: {t.transaction_type}, Status: {t.status}, DocStatus: {t.docstatus}\n"
			else:
				error_msg += "No transactions found for this book and member combination."

			frappe.throw(error_msg)

		# Create return transaction
		from library_management.library_management.doctype.library_transaction.library_transaction import create_return_transaction
		return_doc = create_return_transaction(issue_transaction)

		frappe.set_route('Form', 'Library Transaction', return_doc.name)
		frappe.msgprint(f"Return transaction created for book {self.selected_book}")

		return return_doc.name

	def update_reservation_history_status(self):
		"""Update the status of the corresponding reservation entry in history"""
		try:
			# Get the history record
			history_name = frappe.db.get_value('Library Member History',
				{'member_name': self.member}, 'name')

			if history_name:
				history_doc = frappe.get_doc('Library Member History', history_name)

				# Find the corresponding reservation entry
				for row in history_doc.transaction_history:
					if (row.transaction_type == "Reservation" and
						row.article == self.article and
						row.book == self.selected_book and
						row.status == "Active"):
						row.status = "Reservation Fulfilled"
						row.return_date = frappe.utils.now_datetime()
						break

				history_doc.save(ignore_permissions=True)

		except Exception as e:
			frappe.log_error(f"Error updating reservation history status: {str(e)}")

	@frappe.whitelist()
	def get_available_books(self):
		"""Get available books for the selected article"""
		if not self.article:
			return []

		return frappe.get_all('Book',
			filters={
				'article': self.article,
				'status': 'Available'
			},
			fields=['name', 'copy_number', 'barcode', 'condition', 'location'],
			order_by='copy_number'
		)

	@frappe.whitelist()
	def cancel_reservation(self, reason=""):
		"""Cancel the reservation"""
		if self.status not in ["Active"]:
			frappe.throw("Can only cancel active reservations")

		# Release the reserved book if one was selected
		if self.selected_book:
			try:
				book_doc = frappe.get_doc('Book', self.selected_book)
				book_doc.status = 'Available'
				book_doc.save(ignore_permissions=True)
			except Exception as e:
				frappe.log_error(f"Error releasing reserved book: {str(e)}")

		self.status = "Cancelled"
		self.cancelled_by = frappe.session.user
		self.cancellation_reason = reason
		self.update_cancelled_reservation_history()
		self.save()

		# Notify next person in queue
		self.notify_next_in_queue()

	def update_cancelled_reservation_history(self):
		"""Update the status of cancelled reservation in history"""
		try:
			# Get the history record
			history_name = frappe.db.get_value('Library Member History',
				{'member_name': self.member}, 'name')

			if history_name:
				history_doc = frappe.get_doc('Library Member History', history_name)

				# Find the corresponding reservation entry
				for row in history_doc.transaction_history:
					if (row.transaction_type == "Reservation" and
						row.article == self.article and
						row.book == self.selected_book and
						row.status == "Active"):
						row.status = "Cancelled"
						row.return_date = frappe.utils.now_datetime()
						break

				history_doc.save(ignore_permissions=True)

		except Exception as e:
			frappe.log_error(f"Error updating cancelled reservation history: {str(e)}")

	def notify_next_in_queue(self):
		"""Notify next person in reservation queue"""
		next_reservation = frappe.db.get_value('Book Reservation',
			filters={
				'article': self.article,
				'status': 'Active',
				'docstatus': 1
			},
			fieldname='name',
			order_by='priority_level desc, reservation_date asc'
		)

		if next_reservation:
			next_res_doc = frappe.get_doc('Book Reservation', next_reservation)
			article = frappe.get_doc("Article_New", self.article)

			if article.is_available_for_issue():
				next_res_doc.send_availability_notification()

	def before_save(self):
		"""Check for expiry before saving"""
		if self.status == "Active" and getdate(today()) > getdate(self.expiry_date):
			if not self.notification_sent:
				# Never notified, just expire
				self.status = "Expired"
			else:
				# Was notified but member didn't pick up
				self.status = "Expired"
				self.notify_next_in_queue()

def process_expired_reservations():
	"""Process expired reservations (called by scheduler)"""
	expired_reservations = frappe.get_all('Book Reservation',
		filters={
			'status': 'Active',
			'expiry_date': ['<', today()]
		},
		fields=['name']
	)

	for reservation in expired_reservations:
		doc = frappe.get_doc('Book Reservation', reservation.name)
		doc.status = "Expired"
		doc.save()
		doc.notify_next_in_queue()

	if expired_reservations:
		frappe.db.commit()

def check_article_availability_for_reservations(article):
	"""Check if article becomes available and notify reservations"""
	active_reservations = frappe.get_all('Book Reservation',
		filters={
			'article': article,
			'status': 'Active',
			'docstatus': 1
		},
		fields=['name'],
		order_by='priority_level desc, reservation_date asc',
		limit=1
	)

	if active_reservations:
		reservation_doc = frappe.get_doc('Book Reservation', active_reservations[0].name)
		reservation_doc.send_availability_notification()

def get_reservation_queue(article):
	"""Get reservation queue for a specific article"""
	queue = frappe.get_all('Book Reservation',
		filters={
			'article': article,
			'status': 'Active',
			'docstatus': 1
		},
		fields=['member', 'reservation_date', 'priority_level', 'name'],
		order_by='priority_level desc, reservation_date asc'
	)

	return queue

@frappe.whitelist()
def get_member_reservations(member):
	"""Get all reservations for a specific member"""
	return frappe.get_all('Book Reservation',
		filters={'member': member},
		fields=['name', 'article', 'article_title', 'author', 'status', 'reservation_date', 'expiry_date'],
		order_by='reservation_date desc'
	)

@frappe.whitelist()
def debug_member_article_status(member, article):
	"""Debug member's transaction status for a specific article"""
	if not member or not article:
		return {"error": "Both member and article are required"}

	# Get all transactions for this member and article
	all_transactions = frappe.get_all('Library Transaction',
		filters={
			'library_member': member,
			'article': article
		},
		fields=['name', 'transaction_type', 'status', 'docstatus', 'date', 'return_date', 'book'],
		order_by='creation desc'
	)

	# Check for active issues
	active_issues = frappe.get_all('Library Transaction',
		filters={
			'library_member': member,
			'article': article,
			'transaction_type': 'Issue',
			'status': 'Issued',
			'docstatus': 1
		},
		fields=['name', 'status', 'docstatus', 'date', 'book']
	)

	# Check for returns without corresponding status update
	issue_transactions = [t for t in all_transactions if t.transaction_type == 'Issue']
	return_transactions = [t for t in all_transactions if t.transaction_type == 'Return']

	# Find issues that should be marked as returned
	orphaned_issues = []
	for issue in issue_transactions:
		if issue.status == 'Issued' and issue.docstatus == 1:
			# Check if there's a corresponding return
			corresponding_return = next((r for r in return_transactions
				if r.book == issue.book and r.docstatus == 1), None)
			if corresponding_return:
				orphaned_issues.append({
					'issue': issue,
					'return': corresponding_return
				})

	return {
		'member': member,
		'article': article,
		'total_transactions': len(all_transactions),
		'active_issues': len(active_issues),
		'orphaned_issues': len(orphaned_issues),
		'all_transactions': all_transactions,
		'active_issue_details': active_issues,
		'orphaned_issue_details': orphaned_issues,
		'summary': {
			'has_active_issues': len(active_issues) > 0,
			'has_data_inconsistencies': len(orphaned_issues) > 0
		}
	}

@frappe.whitelist()
def fix_transaction_status_inconsistencies(member, article):
	"""Fix data inconsistencies where issue transactions are not marked as returned"""
	debug_info = debug_member_article_status(member, article)

	if not debug_info.get('orphaned_issues'):
		return {
			'message': 'No data inconsistencies found',
			'fixed_count': 0
		}

	fixed_count = 0
	for orphaned in debug_info['orphaned_issue_details']:
		try:
			issue_doc = frappe.get_doc('Library Transaction', orphaned['issue']['name'])
			issue_doc.status = 'Returned'
			issue_doc.save(ignore_permissions=True)
			fixed_count += 1

			frappe.logger().info(f"Fixed issue transaction {issue_doc.name}: status changed from 'Issued' to 'Returned'")

		except Exception as e:
			frappe.logger().error(f"Error fixing transaction {orphaned['issue']['name']}: {str(e)}")

	if fixed_count > 0:
		frappe.db.commit()

	return {
		'message': f'Fixed {fixed_count} transaction status inconsistencies',
		'fixed_count': fixed_count,
		'total_inconsistencies_found': len(debug_info['orphaned_issue_details'])
	}

@frappe.whitelist()
def get_reservation_workflow_status(reservation_name):
	"""Get complete workflow status for a reservation"""
	reservation = frappe.get_doc('Book Reservation', reservation_name)

	workflow_status = {
		'reservation_status': reservation.status,
		'selected_book': reservation.selected_book,
		'member': reservation.member,
		'article': reservation.article,
		'issue_transaction': None,
		'return_transaction': None,
		'book_status': None
	}

	if reservation.selected_book:
		# Get current book status
		workflow_status['book_status'] = frappe.db.get_value('Book', reservation.selected_book, 'status')

		# Check for issue transaction
		issue_transaction = frappe.db.get_value('Library Transaction', {
			'book': reservation.selected_book,
			'library_member': reservation.member,
			'transaction_type': 'Issue',
			'docstatus': 1
		}, ['name', 'status'], as_dict=True)

		if issue_transaction:
			workflow_status['issue_transaction'] = issue_transaction

			# Check for return transaction
			return_transaction = frappe.db.get_value('Library Transaction', {
				'book': reservation.selected_book,
				'library_member': reservation.member,
				'transaction_type': 'Return',
				'docstatus': 1
			}, ['name', 'status'], as_dict=True)

			if return_transaction:
				workflow_status['return_transaction'] = return_transaction

	return workflow_status