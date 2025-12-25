# Copyright (c) 2023, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import today, getdate

class BookReview(Document):
	def validate(self):
		self.validate_member_eligibility()
		self.validate_duplicate_review()
		self.validate_rating()
		self.validate_review_content()

	def validate_member_eligibility(self):
		"""Validate that member has read the book"""
		# Check if member has issued this book before
		transactions = frappe.db.exists('Library Transaction', {
			'member': self.member,
			'book': self.book,
			'status': 'Returned',
			'docstatus': 1
		})

		if not transactions:
			frappe.throw("You can only review books that you have previously borrowed and returned")

	def validate_duplicate_review(self):
		"""Prevent duplicate reviews from same member for same book"""
		if not self.is_new():
			return

		existing_review = frappe.db.exists('Book Review', {
			'book': self.book,
			'member': self.member,
			'name': ['!=', self.name]
		})

		if existing_review:
			frappe.throw("You have already reviewed this book")

	def validate_rating(self):
		"""Validate rating is within acceptable range"""
		if not (1 <= self.rating <= 5):
			frappe.throw("Rating must be between 1 and 5")

	def validate_review_content(self):
		"""Validate review content"""
		if len(self.review_title.strip()) < 5:
			frappe.throw("Review title must be at least 5 characters long")

		if len(self.review_text.strip()) < 20:
			frappe.throw("Review text must be at least 20 characters long")

		# Check for inappropriate content (basic check)
		inappropriate_words = ['spam', 'fake', 'scam']  # Add more as needed
		text_lower = (self.review_title + ' ' + self.review_text).lower()

		for word in inappropriate_words:
			if word in text_lower:
				self.status = "Pending"
				break

	def before_submit(self):
		"""Actions before submitting review"""
		if self.status == "Rejected":
			frappe.throw("Cannot submit a rejected review")

	def on_submit(self):
		"""Actions after submitting review"""
		if self.status == "Approved":
			# Update book's average rating
			self.update_book_rating()

		# Send notification to librarians for moderation
		if self.status == "Pending":
			self.send_moderation_notification()

	def on_cancel(self):
		"""Actions when review is cancelled"""
		# Update book's average rating
		self.update_book_rating()

	def update_book_rating(self):
		"""Update the book's average rating"""
		book_doc = frappe.get_doc('Book', self.book)
		book_doc.update_availability_status()  # This will recalculate ratings

	def send_moderation_notification(self):
		"""Send notification to librarians for review moderation"""
		librarians = frappe.get_all('User',
			filters={'role_profile_name': 'Librarian'},
			fields=['name', 'email']
		)

		for librarian in librarians:
			frappe.sendmail(
				recipients=[librarian.email],
				subject=f"New Book Review Pending Moderation: {self.book}",
				message=f"""
				A new book review has been submitted and requires moderation.

				Book: {self.book}
				Member: {self.member}
				Rating: {self.rating}/5
				Review Title: {self.review_title}

				Please review and moderate this submission.
				""",
				reference_doctype=self.doctype,
				reference_name=self.name
			)

	@frappe.whitelist()
	def approve_review(self):
		"""Approve the review"""
		self.status = "Approved"
		self.moderated_by = frappe.session.user
		self.moderation_notes = f"Approved on {today()}"
		self.save()
		self.submit()

	@frappe.whitelist()
	def reject_review(self, reason=""):
		"""Reject the review"""
		self.status = "Rejected"
		self.moderated_by = frappe.session.user
		self.moderation_notes = f"Rejected on {today()}. Reason: {reason}"
		self.save()

def get_book_reviews(book, status="Approved", limit=10):
	"""Get reviews for a specific book"""
	reviews = frappe.get_all('Book Review',
		filters={'book': book, 'status': status, 'docstatus': 1},
		fields=['name', 'member', 'rating', 'review_title', 'review_text', 'review_date', 'is_featured'],
		order_by='is_featured desc, review_date desc',
		limit=limit
	)

	return reviews

def get_member_reviews(member, limit=10):
	"""Get reviews by a specific member"""
	reviews = frappe.get_all('Book Review',
		filters={'member': member, 'docstatus': 1},
		fields=['name', 'book', 'rating', 'review_title', 'review_date', 'status'],
		order_by='review_date desc',
		limit=limit
	)

	return reviews