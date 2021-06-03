# Copyright (c) 2013, Frappe
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class LibraryTransaction(Document):
	def validate(self):
		last_transaction = frappe.get_list("Library Transaction",
			fields=["transaction_type", "transaction_date"],
			filters = {
				"article": self.article,
				"transaction_date": ("<=", self.transaction_date),
				"name": ("!=", self.name)
			})
		if self.transaction_type=="Issue":
			if last_transaction and last_transaction[0].transaction_type=="Issue":
				frappe.throw(_("Article {0} {1} has not been recorded as returned since {2}".format(
					self.article, self.article_name, last_transaction[0].transaction_date
				)))
		else:
			if not last_transaction or last_transaction[0].transaction_type!="Issue":
				frappe.throw(_("Cannot return article not issued"))

	def before_submit(self):
		if self.transaction_type == "Issue":
			self.validate_issue()
			# set the article status to be Issued
			article = frappe.get_doc("Article", self.article)
			article.status = "Issued"
			article.save()

		elif self.transaction_type == "Return":
			self.validate_return()
			# set the article status to be Available
			article = frappe.get_doc("Article", self.article)
			article.status = "Available"
			article.save()

	def validate_issue(self):
		self.validate_membership()
		article = frappe.get_doc("Article", self.article)
		# article cannot be issued if it is already issued
		if article.status == "Issued":
			frappe.throw("Article is already issued by another member")

	def validate_return(self):
		article = frappe.get_doc("Article", self.article)
		# article cannot be returned if it is not issued first
		if article.status == "Available":
			frappe.throw("Article cannot be returned without being issued first")

	def validate_membership(self):
		# check if a valid membership exist for this library member
		valid_membership = frappe.db.exists(
			"Library Membership",
			{
				"library_member": self.library_member,
				"docstatus": 1,
				"from_date": ("<", self.transaction_date),
				"to_date": (">", self.transaction_date),
			},
		)
		if not valid_membership:
			frappe.throw("The member does not have a valid membership")