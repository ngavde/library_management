# Copyright (c) 2023, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, add_days, getdate

class BookReservation(Document):
	def validate(self):
		self.validate_member_eligibility()
		self.validate_duplicate_reservation()
		self.set_priority_level()
		self.set_expiry_date()

	def validate_member_eligibility(self):
		"""Validate member can make reservations"""
		member = frappe.get_doc("Library Member", self.member)

		if member.disabled:
			frappe.throw("Cannot create reservation for inactive member")

		# Check if member type allows reservations
		if member.member_type:
			member_type = frappe.get_doc("Member Type", member.member_type)
			if not member_type.can_reserve_books:
				frappe.throw("Your membership type does not allow book reservations")

		# Check for outstanding fines
		total_fine = member.calculate_total_fine()
		if total_fine > 0:
			frappe.throw(f"Cannot create reservation. Outstanding fines: ${total_fine}")

		# Check if member already has this book issued
		if frappe.db.exists('Library Transaction', {
			'member': self.member,
			'book': self.book,
			'status': 'Issued',
			'docstatus': 1
		}):
			frappe.throw("You already have this book issued")

	def validate_duplicate_reservation(self):
		"""Prevent duplicate active reservations"""
		if not self.is_new():
			return

		existing_reservation = frappe.db.exists('Book Reservation', {
			'book': self.book,
			'member': self.member,
			'status': 'Active',
			'name': ['!=', self.name]
		})

		if existing_reservation:
			frappe.throw("You already have an active reservation for this book")

	def set_priority_level(self):
		"""Set priority based on member type"""
		member = frappe.get_doc("Library Member", self.member)

		if member.member_type:
			member_type = frappe.get_doc("Member Type", member.member_type)
			if member_type.priority_reservations:
				self.priority_level = member_type.priority_level
			else:
				self.priority_level = 1  # Standard priority
		else:
			self.priority_level = 1

	def set_expiry_date(self):
		"""Set reservation expiry date"""
		if not self.expiry_date:
			# Default 7 days from reservation date
			self.expiry_date = add_days(self.reservation_date, 7)

	def on_submit(self):
		"""Actions after submitting reservation"""
		self.check_book_availability()

	def check_book_availability(self):
		"""Check if book is immediately available"""
		book = frappe.get_doc("Book", self.book)

		if book.is_available_for_issue():
			# Book is available, notify member immediately
			self.send_availability_notification()
		else:
			# Book not available, add to queue
			queue_position = self.get_queue_position()
			if queue_position <= 1:
				frappe.msgprint(f"You are next in queue for '{self.book}'")

	def send_availability_notification(self):
		"""Send notification when book becomes available"""
		if self.notification_sent:
			return

		member = frappe.get_doc("Library Member", self.member)

		if member.email_address:
			frappe.sendmail(
				recipients=[member.email_address],
				subject=f"Book Available for Pickup: {self.book}",
				message=f"""
				Dear {member.full_name},

				The book "{self.book}" that you reserved is now available for pickup.

				Please visit the library within 3 days to collect your book.
				After this period, the reservation will expire and the book will be available to the next person in queue.

				Best regards,
				Library Management System
				""",
				reference_doctype=self.doctype,
				reference_name=self.name
			)

			self.notification_sent = 1
			self.notified_date = today()
			self.save()

	def get_queue_position(self):
		"""Get position in reservation queue"""
		reservations_ahead = frappe.db.count('Book Reservation', {
			'book': self.book,
			'status': 'Active',
			'reservation_date': ['<', self.reservation_date],
			'priority_level': ['>=', self.priority_level],
			'docstatus': 1
		})

		# Also count higher priority reservations made after this one
		higher_priority = frappe.db.count('Book Reservation', {
			'book': self.book,
			'status': 'Active',
			'priority_level': ['>', self.priority_level],
			'docstatus': 1
		})

		return reservations_ahead + higher_priority + 1

	@frappe.whitelist()
	def fulfill_reservation(self):
		"""Mark reservation as fulfilled when book is issued"""
		if self.status != "Active":
			frappe.throw("Can only fulfill active reservations")

		self.status = "Fulfilled"
		self.save()

		# Notify next person in queue
		self.notify_next_in_queue()

	@frappe.whitelist()
	def cancel_reservation(self, reason=""):
		"""Cancel the reservation"""
		if self.status not in ["Active"]:
			frappe.throw("Can only cancel active reservations")

		self.status = "Cancelled"
		self.cancelled_by = frappe.session.user
		self.cancellation_reason = reason
		self.save()

		# Notify next person in queue
		self.notify_next_in_queue()

	def notify_next_in_queue(self):
		"""Notify next person in reservation queue"""
		next_reservation = frappe.db.get_value('Book Reservation',
			filters={
				'book': self.book,
				'status': 'Active',
				'docstatus': 1
			},
			fieldname='name',
			order_by='priority_level desc, reservation_date asc'
		)

		if next_reservation:
			next_res_doc = frappe.get_doc('Book Reservation', next_reservation)
			book = frappe.get_doc("Book", self.book)

			if book.is_available_for_issue():
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

def check_book_availability_for_reservations(book):
	"""Check if book becomes available and notify reservations"""
	active_reservations = frappe.get_all('Book Reservation',
		filters={
			'book': book,
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

def get_reservation_queue(book):
	"""Get reservation queue for a specific book"""
	queue = frappe.get_all('Book Reservation',
		filters={
			'book': book,
			'status': 'Active',
			'docstatus': 1
		},
		fields=['member', 'reservation_date', 'priority_level', 'name'],
		order_by='priority_level desc, reservation_date asc'
	)

	return queue