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
		"""Validate that member has read the article"""
		# Check if member has issued this article before
		transactions = frappe.db.exists('Library Transaction', {
			'library_member': self.member,
			'article': self.article,
			'status': 'Returned',
			'docstatus': 1
		})

		if not transactions:
			frappe.throw("You can only review articles that you have previously borrowed and returned")

		# Check if member is active
		member_doc = frappe.get_doc('Library Member', self.member)
		if getattr(member_doc, 'disabled', False):
			frappe.throw("Inactive members cannot submit reviews")

	def validate_duplicate_review(self):
		"""Prevent duplicate reviews from same member for same article"""
		if not self.is_new():
			return

		existing_review = frappe.db.exists('Book Review', {
			'article': self.article,
			'member': self.member,
			'name': ['!=', self.name]
		})

		if existing_review:
			frappe.throw("You have already reviewed this article")

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
		inappropriate_words = ['spam', 'fake', 'scam', 'offensive']  # Add more as needed
		text_lower = (self.review_title + ' ' + self.review_text).lower()

		for word in inappropriate_words:
			if word in text_lower:
				self.status = "Pending"
				break

	def before_submit(self):
		"""Actions before submitting review"""
		if self.status == "Rejected":
			frappe.throw("Cannot submit a rejected review")

		# Auto-approve if no moderation is needed
		if self.status != "Pending":
			self.status = "Approved"

	def on_submit(self):
		"""Actions after submitting review"""
		if self.status == "Approved":
			# Update article's rating summary
			self.update_article_rating()

		# Send notification to librarians for moderation
		if self.status == "Pending":
			self.send_moderation_notification()

	def on_cancel(self):
		"""Actions when review is cancelled"""
		# Update article's rating summary
		self.update_article_rating()

	def update_article_rating(self):
		"""Update the article's average rating"""
		try:
			article_doc = frappe.get_doc('Article_New', self.article)
			# Trigger refresh of rating statistics
			average_rating = article_doc.get_average_rating()
			total_reviews = article_doc.get_total_reviews()

			# Store these values if article has custom fields for them
			if hasattr(article_doc, 'average_rating'):
				article_doc.average_rating = average_rating
			if hasattr(article_doc, 'total_reviews'):
				article_doc.total_reviews = total_reviews

			article_doc.save(ignore_permissions=True)
		except Exception as e:
			frappe.log_error(f"Error updating article rating: {str(e)}")

	def send_moderation_notification(self):
		"""Send notification to librarians for review moderation"""
		try:
			librarians = frappe.get_all('User',
				filters={'role_profile_name': 'Librarian'},
				fields=['name', 'email']
			)

			for librarian in librarians:
				if librarian.email:
					frappe.sendmail(
						recipients=[librarian.email],
						subject=f"New Article Review Pending Moderation: {self.article_title}",
						message=f"""
						A new article review has been submitted and requires moderation.

						Article: {self.article_title}
						Author: {self.author}
						Member: {self.member}
						Rating: {self.rating}/5
						Review Title: {self.review_title}

						Please review and moderate this submission in the Library Management system.

						Best regards,
						Library Management System
						""",
						reference_doctype=self.doctype,
						reference_name=self.name
					)
		except Exception as e:
			frappe.log_error(f"Error sending moderation notification: {str(e)}")

	@frappe.whitelist()
	def approve_review(self):
		"""Approve the review"""
		if self.docstatus != 0:
			frappe.throw("Can only approve draft reviews")

		self.status = "Approved"
		self.moderated_by = frappe.session.user
		self.moderation_notes = f"Approved on {today()}"
		self.save()
		self.submit()

		frappe.msgprint("Review has been approved and published")

	@frappe.whitelist()
	def reject_review(self, reason=""):
		"""Reject the review"""
		if self.docstatus != 0:
			frappe.throw("Can only reject draft reviews")

		self.status = "Rejected"
		self.moderated_by = frappe.session.user
		self.moderation_notes = f"Rejected on {today()}. Reason: {reason}"
		self.save()

		frappe.msgprint("Review has been rejected")

	@frappe.whitelist()
	def feature_review(self):
		"""Mark review as featured"""
		if self.status != "Approved":
			frappe.throw("Only approved reviews can be featured")

		self.is_featured = 1
		self.save()

		frappe.msgprint("Review has been marked as featured")

def get_article_reviews(article, status="Approved", limit=10):
	"""Get reviews for a specific article"""
	reviews = frappe.get_all('Book Review',
		filters={'article': article, 'status': status, 'docstatus': 1},
		fields=['name', 'member', 'rating', 'review_title', 'review_text', 'review_date', 'is_featured'],
		order_by='is_featured desc, review_date desc',
		limit=limit
	)

	# Add member name for display
	for review in reviews:
		try:
			member_doc = frappe.get_doc('Library Member', review.member)
			review.member_name = getattr(member_doc, 'full_name', review.member)
		except:
			review.member_name = review.member

	return reviews

def get_member_reviews(member, limit=10):
	"""Get reviews by a specific member"""
	reviews = frappe.get_all('Book Review',
		filters={'member': member, 'docstatus': 1},
		fields=['name', 'article', 'article_title', 'author', 'rating', 'review_title', 'review_date', 'status'],
		order_by='review_date desc',
		limit=limit
	)

	return reviews

def get_featured_reviews(limit=5):
	"""Get featured reviews for homepage/dashboard"""
	reviews = frappe.get_all('Book Review',
		filters={'status': 'Approved', 'is_featured': 1, 'docstatus': 1},
		fields=['name', 'article', 'article_title', 'author', 'member', 'rating', 'review_title', 'review_text', 'review_date'],
		order_by='review_date desc',
		limit=limit
	)

	# Add member names
	for review in reviews:
		try:
			member_doc = frappe.get_doc('Library Member', review.member)
			review.member_name = getattr(member_doc, 'full_name', review.member)
		except:
			review.member_name = review.member

	return reviews

def get_pending_reviews():
	"""Get all pending reviews for moderation"""
	return frappe.get_all('Book Review',
		filters={'status': 'Pending', 'docstatus': 0},
		fields=['name', 'article', 'article_title', 'author', 'member', 'rating', 'review_title', 'review_date'],
		order_by='review_date asc'
	)

@frappe.whitelist()
def get_review_statistics(article=None):
	"""Get review statistics for an article or overall"""
	filters = {'status': 'Approved', 'docstatus': 1}
	if article:
		filters['article'] = article

	# Get rating distribution
	rating_stats = frappe.db.sql("""
		SELECT rating, COUNT(*) as count
		FROM `tabBook Review`
		WHERE status = 'Approved' AND docstatus = 1
		{article_filter}
		GROUP BY rating
		ORDER BY rating
	""".format(
		article_filter=f"AND article = '{article}'" if article else ""
	), as_dict=True)

	# Calculate average and total
	total_reviews = sum(stat.count for stat in rating_stats)
	if total_reviews > 0:
		weighted_sum = sum(stat.rating * stat.count for stat in rating_stats)
		average_rating = round(weighted_sum / total_reviews, 2)
	else:
		average_rating = 0

	return {
		'rating_distribution': rating_stats,
		'average_rating': average_rating,
		'total_reviews': total_reviews
	}