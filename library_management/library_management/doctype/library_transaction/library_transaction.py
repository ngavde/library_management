# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
<<<<<<< HEAD
from frappe.utils import today, getdate, add_days

class LibraryTransaction(Document):
	def validate(self):
		self.validate_member_eligibility()
		self.validate_book_availability()
		self.validate_return_permission()
		self.set_due_date()

	def validate_member_eligibility(self):
		"""Validate member eligibility for borrowing"""
		if self.status == "Issued":
			member = frappe.get_doc("Library Member", self.member)

			# Check if member is active
			if member.disabled:
				frappe.throw("Cannot issue book to inactive member")

			# Get member type limits
			if member.member_type:
				member_type = frappe.get_doc("Member Type", member.member_type)

				# Check current books issued
				current_books = frappe.db.count('Library Transaction', {
					'member': self.member,
					'status': 'Issued',
					'docstatus': 1
				})

				if current_books >= member_type.max_books_allowed:
					frappe.throw(f"Member has reached maximum limit of {member_type.max_books_allowed} books")

	def validate_book_availability(self):
		"""Validate book is available for issue"""
		if self.status == "Issued":
			book = frappe.get_doc("Book", self.book)

			if not book.is_available_for_issue():
				frappe.throw("Book is not available for issue")

	def validate_return_permission(self):
		"""Validate only the borrower can return the book"""
		if self.status == "Returned":
			last_issue = frappe.db.get_value('Library Transaction',
				filters={
					'book': self.book,
					'status': 'Issued',
					'docstatus': 1
				},
				fieldname=['member', 'name'],
				order_by='creation desc'
			)

			if last_issue and last_issue[0] != self.member:
				frappe.throw(f"Only {last_issue[0]} can return this book")

	def set_due_date(self):
		"""Set due date based on member type"""
		if self.status == "Issued" and not self.due_date:
			member = frappe.get_doc("Library Member", self.member)

			if member.member_type:
				member_type = frappe.get_doc("Member Type", member.member_type)
				self.due_date = add_days(self.date, member_type.loan_period_days)
			else:
				# Default loan period from settings
				settings = frappe.get_single("Library Settings")
				self.due_date = add_days(self.date, settings.loan_period or 14)

	def before_submit(self):
		"""Actions before submitting transaction"""
		if self.status == "Issued":
			self.issue_book()
		elif self.status == "Returned":
			self.return_book()

	def issue_book(self):
		"""Process book issue"""
		# Update book availability
		book = frappe.get_doc("Book", self.book)
		book.available_copies = max(0, book.available_copies - 1)
		if book.available_copies == 0:
			book.status = "Issued"
		book.save()

		# Update member history
		self.update_member_history("Issued")

	def return_book(self):
		"""Process book return"""
		# Update book availability
		book = frappe.get_doc("Book", self.book)
		book.available_copies = min(book.total_copies, book.available_copies + 1)
		if book.available_copies > 0:
			book.status = "Available"
		book.save()

		# Calculate fine if overdue
		self.calculate_fine()

		# Update member history
		self.update_member_history("Returned")

	def calculate_fine(self):
		"""Calculate fine for overdue books"""
		if not self.due_date:
			return

		days_overdue = (getdate(today()) - getdate(self.due_date)).days

		if days_overdue > 0:
			member = frappe.get_doc("Library Member", self.member)
			if member.member_type:
				member_type = frappe.get_doc("Member Type", member.member_type)
				fine_per_day = member_type.late_fee_per_day
			else:
				# Default fine from settings
				settings = frappe.get_single("Library Settings")
				fine_per_day = settings.late_fee_per_day or 1.0

			self.fine_amount = days_overdue * fine_per_day
			self.days_overdue = days_overdue

	def update_member_history(self, status):
		"""Update member transaction history"""
		# Check if member history exists
		member_history = frappe.db.exists('Library Member History', {'member_name': self.member})

		if member_history:
			doc = frappe.get_doc("Library Member History", member_history)
		else:
			doc = frappe.new_doc('Library Member History')
			doc.member_name = self.member

		doc.append("transaction_history", {
			"book": self.book,
			"author": self.author,
			"isbn": self.isbn,
			"transaction_date": self.date,
			"transaction_status": status,
			"due_date": self.due_date,
			"fine_amount": self.fine_amount or 0
		})
		doc.save()

	@frappe.whitelist()
	def renew_book(self, renewal_period=None):
		"""Renew book for additional period"""
		if self.status != "Issued":
			frappe.throw("Can only renew issued books")

		member = frappe.get_doc("Library Member", self.member)

		# Check renewal eligibility
		if member.member_type:
			member_type = frappe.get_doc("Member Type", member.member_type)

			if not member_type.can_renew_online:
				frappe.throw("Online renewal not allowed for your membership type")

			# Check renewal count
			renewal_count = frappe.db.count('Library Transaction', {
				'book': self.book,
				'member': self.member,
				'transaction_type': 'Renewal',
				'docstatus': 1
			})

			if renewal_count >= member_type.max_renewals_allowed:
				frappe.throw(f"Maximum {member_type.max_renewals_allowed} renewals allowed")

			renewal_days = renewal_period or member_type.renewal_period_days
		else:
			renewal_days = renewal_period or 7

		# Create renewal transaction
		renewal = frappe.new_doc('Library Transaction')
		renewal.update({
			'book': self.book,
			'member': self.member,
			'transaction_type': 'Renewal',
			'date': today(),
			'due_date': add_days(self.due_date, renewal_days),
			'status': 'Renewed'
		})
		renewal.submit()

		# Update current transaction due date
		self.due_date = renewal.due_date
		self.save()

		return renewal
=======

class LibraryTransaction(Document):	

	def on_submit(self):
		if self.type == 'Available' :
			self.status = 'Issued'

		if (self.type == 'Issued' and self.returned == 1):
			self.status ='Returned'

		if (self.type == 'Available'):
			a = frappe.get_doc("Article_New",{'article_name':self.article})
			# print('55555555555555555555555',a)
			a.status ='Issued'
			# a.return_status = 'Issued'
			a.save()

		if (self.type == 'Issued' and self.returned == 1):
			b = frappe.get_doc("Article_New",{'article_name':self.article})
			b.status = 'Available'
			# b.return_status = 'Available'
			b.save()

		
#       APPENDING DATA TO CHILD TABLE
		lst=[]
		lst_lib_member=frappe.db.get_list("Library Member History",{"docstatus":0},["member_name"])

		for i in lst_lib_member:
			lst.append(i.get("member_name"))
		if self.library_membe in lst:
			doc=frappe.get_doc("Library Member History",{"member_name":self.library_membe})
			doc.append("transaction_history",{
				"article" : self.article,
				"author": self.author,
				"isbn":  self.isbn,
				"transaction_date": self.date,
				"transaction_status":self.status,
				})
			doc.save()
		else:
			library_mem_his = frappe.new_doc('Library Member History')
			library_mem_his.member_name = self.library_membe
			
			library_mem_his.append("transaction_history",{
				"article" : self.article,
				"author": self.author,
				"isbn":  self.isbn,
				"transaction_date": self.date,
				"transaction_status":self.status

			})
			library_mem_his.save()

	
	
# Book can be returned by those who borrowed it.
	def before_save(self):
		if self.returned == 1:
			task = frappe.get_last_doc('Library Transaction', filters={"status": "Taken","docstatus":1,"article":self.article})
			print('88888888888888888',task)
			if self.library_membe != task.library_membe and self.returned == 1 and self.article == task.article:
				frappe.throw(f"{task.library_membe} has borrowed this book, only he can return.")
			
	
			
			

	# def before_save(self):

	# 	d = frappe.get_doc("Library Member History",{"member_name":self.library_membe})
	# 	print('////////////////////',d)
	
	# 	for i in d.transaction_history:
	# 		if self.article == i.article and i.transaction_status == 'Issued':
	# 			print("*********************",i.article,d.member_name)
	# 		else:
	# 			frappe.throw(f"{self.library_membe} has not borrowed this book")
		

		
		
		
			



		
	# def validate(self):
	# 	d1 = frappe.db.get_value("Library Member History",{"member_name":self.library_membe},['name'])
	# 	if d1:
	# 		d = frappe.get_doc('Library Member History',d1)
	# 		print('**********************',d.member_name)
	# 		if self.library_membe == d.member_name and  self.returned == 1:
	# 			print('************2222222222222s**********',d.member_name)
	# 			for article in d.transaction_history:
	# 				if article.article == self.article and article.transaction_status == "Issued" :
	# 					print(self.library_membe,d.member_name,self.returned)
				
			
	# 		elif self.library_membe != d.member_name and  self.returned == 1:
	# 			print(self.library_membe,d.member_name,self.returned)
	# 			frappe.throw(f"{self.library_membe} has not taken this book hence cannot return.")
			
				

		
	

	

		
		# if (self.type == 'Issued' and self.returned == 1):
		# 	b = frappe.get_doc("Article_New",{'status':'Issued'})
		# 	b.status == 'Available'
		# 	b.save()



		# def returned(self):
		# 	if(self.type == 'Issued'):
				
					
					

	
		# a = frappe.db.get_list('Library Member',
		# 	filters={
		# 		'check': 1
		# 	},)
		# # print('8888888888888888',a)


		# a =	frappe.db.get_value('Library Member', {'check': '1'})
		# print('///////////',a)
		


		# print("5555555555555555555",frappe.db.get_value('Article_New','Communication Skills', 'author'))
		# print('1111111111111111',frappe.db.exists('Library Member History','','David'))

		# a = frappe.db.exists('Library Member History', 'LM-0002') 
		
		
		# if a == True:
		
		# 	library_mem_his.append("transaction_history",{
		# 		"article" : self.article,
		# 		"author": self.author,
		# 		"isbn":  self.isbn,
		# 		"transaction_date": self.date,
		# 		"status":self.type

		# 	})
		# 	library_mem_his.save()







	# def library_member(self):
	# 	lib_art = frappe.new_doc('Article_New')
	# 	library_mem_his.article = self.article 
	# 	library_mem_his.isbn = lib_art.isbn
	# 	library_mem_his.author = lib_art.author
	# 	library_mem_his.transaction_date = self.date
	# 	library_mem_his.save()
>>>>>>> 77745fb (Changes)
