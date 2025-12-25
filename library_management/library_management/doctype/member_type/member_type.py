# Copyright (c) 2023, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class MemberType(Document):
	def validate(self):
		self.validate_priority_level()
		self.validate_fees()
		self.validate_borrowing_limits()

	def validate_priority_level(self):
		"""Validate priority level is within acceptable range"""
		if not (1 <= self.priority_level <= 10):
			frappe.throw("Priority level must be between 1 and 10")

	def validate_fees(self):
		"""Validate fee amounts"""
		if self.membership_fee_annual < 0:
			frappe.throw("Annual membership fee cannot be negative")

		if self.late_fee_per_day < 0:
			frappe.throw("Late fee per day cannot be negative")

		if self.reservation_fee < 0:
			frappe.throw("Reservation fee cannot be negative")

		if self.processing_fee < 0:
			frappe.throw("Processing fee cannot be negative")

	def validate_borrowing_limits(self):
		"""Validate borrowing limits"""
		if self.max_books_allowed <= 0:
			frappe.throw("Maximum books allowed must be greater than 0")

		if self.loan_period_days <= 0:
			frappe.throw("Loan period must be greater than 0 days")

		if self.max_renewals_allowed < 0:
			frappe.throw("Maximum renewals allowed cannot be negative")

		if self.renewal_period_days < 0:
			frappe.throw("Renewal period cannot be negative")

	def on_update(self):
		"""Actions when member type is updated"""
		if self.has_value_changed('disabled') and self.disabled:
			self.validate_disable()

	def validate_disable(self):
		"""Validate before disabling member type"""
		active_members = frappe.db.count('Library Member', {
			'member_type': self.name,
			'disabled': 0
		})

		if active_members > 0:
			frappe.throw(f"Cannot disable member type. {active_members} active members are using this type")

	def get_members_count(self):
		"""Get total number of members of this type"""
		return frappe.db.count('Library Member', {'member_type': self.name})

	def get_active_members_count(self):
		"""Get number of active members of this type"""
		return frappe.db.count('Library Member', {
			'member_type': self.name,
			'disabled': 0
		})

	@frappe.whitelist()
	def get_member_type_stats(self):
		"""Get comprehensive member type statistics"""
		stats = {
			'total_members': self.get_members_count(),
			'active_members': self.get_active_members_count()
		}

		# Get borrowing statistics
		borrowing_stats = frappe.db.sql("""
			SELECT
				COUNT(DISTINCT lm.name) as members_with_books,
				COUNT(lt.name) as total_books_issued,
				AVG(DATEDIFF(CURDATE(), lt.issue_date)) as avg_loan_period
			FROM `tabLibrary Member` lm
			LEFT JOIN `tabLibrary Transaction` lt ON lm.name = lt.member AND lt.status = 'Issued'
			WHERE lm.member_type = %s AND lm.disabled = 0
		""", [self.name], as_dict=True)

		if borrowing_stats:
			stats.update(borrowing_stats[0])

		return stats

def get_default_member_type():
	"""Get the default member type (lowest priority level)"""
	member_type = frappe.db.get_value('Member Type',
		filters={'disabled': 0},
		fieldname='name',
		order_by='priority_level ASC'
	)

	return member_type

def create_default_member_types():
	"""Create default member types if they don't exist"""
	default_types = [
		{
			'member_type_name': 'Student',
			'description': 'Student membership with basic privileges',
			'priority_level': 1,
			'max_books_allowed': 3,
			'loan_period_days': 14,
			'max_renewals_allowed': 2,
			'renewal_period_days': 7,
			'membership_fee_annual': 20.00,
			'late_fee_per_day': 0.50,
			'can_reserve_books': 1,
			'can_renew_online': 1,
			'color': '#3498db'
		},
		{
			'member_type_name': 'Faculty',
			'description': 'Faculty membership with extended privileges',
			'priority_level': 3,
			'max_books_allowed': 10,
			'loan_period_days': 30,
			'max_renewals_allowed': 5,
			'renewal_period_days': 14,
			'membership_fee_annual': 0.00,
			'late_fee_per_day': 1.00,
			'can_reserve_books': 1,
			'can_renew_online': 1,
			'priority_reservations': 1,
			'color': '#e74c3c'
		},
		{
			'member_type_name': 'Premium',
			'description': 'Premium membership with maximum privileges',
			'priority_level': 5,
			'max_books_allowed': 20,
			'loan_period_days': 45,
			'max_renewals_allowed': 10,
			'renewal_period_days': 21,
			'membership_fee_annual': 100.00,
			'late_fee_per_day': 2.00,
			'can_reserve_books': 1,
			'can_renew_online': 1,
			'priority_reservations': 1,
			'color': '#f39c12'
		}
	]

	for member_type_data in default_types:
		if not frappe.db.exists('Member Type', member_type_data['member_type_name']):
			member_type = frappe.new_doc('Member Type')
			member_type.update(member_type_data)
			member_type.insert(ignore_permissions=True)