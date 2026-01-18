# Copyright (c) 2022, Vtech Technologies and Contributors
# See license.txt

import frappe
import unittest
from library_management.library_management.doctype.library_member_history.library_member_history import LibraryMemberHistory

class TestLibraryMemberHistory(unittest.TestCase):
	def setUp(self):
		# Clean up any existing test data
		frappe.db.rollback()
		frappe.delete_doc_if_exists("Library Member History", "test-member-1", ignore_missing=True)

	def test_single_history_per_member(self):
		"""Test that only one history record exists per member"""
		member_name = "test-member-1"

		# Create first history record
		history1 = LibraryMemberHistory.get_or_create_history(member_name)
		self.assertIsNotNone(history1)

		# Try to get history again - should return the same record
		history2 = LibraryMemberHistory.get_or_create_history(member_name)
		self.assertEqual(history1.name, history2.name)

	def test_add_multiple_transactions(self):
		"""Test adding multiple transaction lines to the same member"""
		member_name = "test-member-1"

		# Add first transaction
		LibraryMemberHistory.add_transaction_to_history(
			member_name=member_name,
			article="Book 1",
			author="Author 1",
			transaction_status="Issued"
		)

		# Add second transaction
		LibraryMemberHistory.add_transaction_to_history(
			member_name=member_name,
			article="Book 2",
			author="Author 2",
			transaction_status="Returned"
		)

		# Verify only one history record exists with two transaction lines
		history_records = frappe.get_all("Library Member History",
			filters={"member_name": member_name})
		self.assertEqual(len(history_records), 1)

		history_doc = frappe.get_doc("Library Member History", history_records[0].name)
		self.assertEqual(len(history_doc.transaction_history), 2)
