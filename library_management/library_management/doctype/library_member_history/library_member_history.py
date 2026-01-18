# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class LibraryMemberHistory(Document):
	def validate(self):
		# Ensure only one history record per member
		if not self.is_new():
			return

		existing_history = frappe.get_all("Library Member History",
			filters={"member_name": self.member_name, "name": ["!=", self.name]})

		if existing_history:
			frappe.throw(f"History record already exists for member {self.member_name}")

	@staticmethod
	def get_or_create_history(member_name):
		"""Get existing history record or create new one for a member"""
		existing_history = frappe.get_all("Library Member History",
			filters={"member_name": member_name}, limit=1)

		if existing_history:
			return frappe.get_doc("Library Member History", existing_history[0].name)
		else:
			# Create new history record
			history_doc = frappe.new_doc("Library Member History")
			history_doc.member_name = member_name
			history_doc.save()
			return history_doc

	@staticmethod
	def add_transaction_to_history(member_name, article=None, author=None, isbn=None, transaction_status=None, transaction_date=None):
		"""Add a transaction line to the member's history"""
		history_doc = LibraryMemberHistory.get_or_create_history(member_name)

		history_doc.append("transaction_history", {
			"article": article,
			"author": author,
			"isbn": isbn,
			"transaction_status": transaction_status,
			"transaction_date": transaction_date
		})

		history_doc.save()
		return history_doc
