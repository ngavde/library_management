# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class LibraryMemberHistory(Document):
	pass
	# appending data in child table of same doctype
	# def before_save(self):
	# 	a = self.member_name

	# 	self.append("transaction_history",{
	# 		"article":self.member_first_name
	# 	})
			
