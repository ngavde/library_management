# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class LibraryTransaction(Document):

	def validate(self):
		# Ensure either article or book is specified, but not both
		# Use getattr to handle cases where book field doesn't exist yet
		book_value = getattr(self, 'book', None)

		if not self.article and not book_value:
			frappe.throw("Either Article or Book must be specified for a transaction")

		if self.article and book_value:
			frappe.throw("Cannot specify both Article and Book in the same transaction")

	def on_submit(self):
		if self.type == 'Available' :
			self.status = 'Issued'

		if (self.type == 'Issued' and self.returned == 1):
			self.status ='Returned'

		# Handle Article_New transactions
		if (self.type == 'Available' and self.article):
			try:
				a = frappe.get_doc("Article_New", self.article)
				a.status ='Issued'
				a.save()
			except Exception as e:
				frappe.log_error(f"Error updating Article_New status: {str(e)}")

		if (self.type == 'Issued' and self.returned == 1 and self.article):
			try:
				b = frappe.get_doc("Article_New", self.article)
				b.status = 'Available'
				b.save()
			except Exception as e:
				frappe.log_error(f"Error updating Article_New status on return: {str(e)}")

		# Handle Book transactions
		book_value = getattr(self, 'book', None)
		if (self.status == 'Issued' and book_value):
			try:
				book_doc = frappe.get_doc("Book", book_value)
				book_doc.update_availability_status()
				book_doc.save()
			except Exception as e:
				frappe.log_error(f"Error updating Book status: {str(e)}")

		
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
			# Handle Article_New return validation
			if self.article:
				try:
					task = frappe.get_last_doc('Library Transaction', filters={"status": "Taken","docstatus":1,"article":self.article})
					if task and self.library_membe != task.library_membe and self.returned == 1 and self.article == task.article:
						frappe.throw(f"{task.library_membe} has borrowed this book, only he can return.")
				except Exception as e:
					frappe.log_error(f"Error validating Article_New return: {str(e)}")

			# Handle Book return validation
			book_value = getattr(self, 'book', None)
			if book_value:
				try:
					task = frappe.get_last_doc('Library Transaction', filters={"status": "Issued","docstatus":1,"book":book_value})
					if task and self.library_membe != task.library_membe:
						frappe.throw(f"{task.library_membe} has borrowed this book, only he can return.")
				except Exception as e:
					frappe.log_error(f"Error validating Book return: {str(e)}")
			
	
			
			

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
