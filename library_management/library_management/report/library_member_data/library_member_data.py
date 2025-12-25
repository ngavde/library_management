# Copyright (c) 2022, Vtech Technologies and contributors
# For license information, please see license.txt

from dbm.ndbm import library
import frappe

def execute(filters=None):
	
	message = 'This is Library Member Data'
	columns = [{'fieldname':'member_name','label':'Member Name','fieldtype':'Data'},{'fieldname':'member_first_name','label':'First Name','fieldtype':'Data'},
        {'fieldname':'member_last_name','label':'Last Name','fieldtype':'Data'},
        {'fieldname':'email','label':'Email','fieldtype':'Data'},
		{'fieldname':'article','label':'Article','fieldtype':'Data'},
		{'fieldname':'transaction_status','label':'Transaction Status','fieldtype':'Data'},
		{'fieldname':'transaction_date','label':'Transaction Date','fieldtype':'Date'},
		

]


	# data = frappe.db.sql('''SELECT t1.member_first_name, t1.member_last_name, t1.email, t2.article,
	# t2.transaction_status, t2.transaction_date
	# FROM `tabLibrary Member History` as t1 
	# JOIN `tabLibrary Child Table` as t2 ON t2.parent=t1.name  ''')
# 	print('*******************',data)

	# columns = get_columns(filters)
	conditions = get_conditions(filters)
	data = get_data(conditions, filters)
	empty_dict = {"name":[],"member_first_name":[],"member_last_nmae":[]}

	for d in data:
		for i in d:
			lib_mem = frappe.get_list("Library Member",["name"])
			# print("llllllllllllllllllllllllllllll",lib_mem)
			for e in lib_mem:
				if e.name in i:
					i.member_first_name = "empty"
			print('5555555555555555555',d)

		# print('************************************',d)
	return columns, data, message
	


def get_conditions(filters):
	print("This is from get_conditions(filters)")
	conditions = ""

	if filters.get("from_date") > filters.get("to_date"):		
		frappe.throw("The 'From Date' ({}) must be before the 'To Date' ({})".format(filters.get("from_date"), filters.get("to_date")))

	if filters.get("from_date") and filters.get("to_date"):	
		conditions += " t2.transaction_date between '{0}' and '{1}'".format(filters.get("from_date"),filters.get("to_date"))
		print('//////////////////',filters.get("from_date"))

	if filters.get("article"):
		conditions += "AND t2.article  = '{0}'".format(filters.get("article"))

	if filters.get("status"):
		conditions += "AND t2.transaction_status = '{0}'".format(filters.get("status"))

	if filters.get("first_name"):
		conditions += "AND t1.member_name = '{0}'".format(filters.get("first_name"))

	
	

	return conditions




def get_data(conditions, filters):
	query = frappe.db.sql('''SELECT t1.name, t1.member_first_name, t1.member_last_name, t1.email, t2.article,
	t2.transaction_status, t2.transaction_date
	FROM `tabLibrary Member History` as t1 
	JOIN `tabLibrary Child Table` as t2 ON t2.parent=t1.name
	where {0} '''.format(conditions),filters,as_dict=1)
	return query
	 





		

	# data = frappe.db.get_all('Library Member History',['member_first_name','member_last_name','email'])
	# print('555555555555555555',data)
	
	# data = []
	# parent = frappe.db.sql("SELECT t1.member_first_name, t1.member_last_name, t1.email, t2.article FROM `tabLibrary Member History` AS t1 JOIN `tabLibrary Child Table` AS t2 ON t2.parent = t1.name", as_dict=1)
	# #frappe.msgprint("<pre>{}</pre>".format(frappe.as_json(parent)))
	# for dic_p in parent:
	# 	dic_p["indent"] = 0
	# 	data.append(dic_p)
	# 	#frappe.msgprint(dic_p["name"])
	# 	child = frappe.db.sql("SELECT transaction_status, transaction_date FROM `tabLibrary Child Table`  ", as_dict=1)
	# 	#frappe.msgprint("<pre>{}</pre>".format(frappe.as_json(child)))
	# 	for dic_c in child:
	# 		dic_c["indent"] = 1
	# 		data.append(dic_c)
	
	
	# return columns, data, message



# fieldname in data and columns should be same.