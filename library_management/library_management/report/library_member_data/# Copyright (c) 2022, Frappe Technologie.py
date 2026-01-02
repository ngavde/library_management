# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	# message = ["This is sample script report"]
    columns = [
        
        {'fieldname':'first_name','label':'First Name','fieldtype':'Data'},
        {'fieldname':'last_name','label':'Last Name','fieldtype':'Data'},
        {'fieldname':'email_address','label':'Email','fieldtype':'Data'}

        
    ]
    data = frappe.db.get_all('Library Member', ['first_name','last_name','email_address'])
    # frappe.msgprint("<span style='color:Red;'>Once this popup has served it's purpose, then comment out it's invocation, viz. #frappe.msgprint...</span><br><br>" + "<pre>{}</pre>".format(frappe.as_json(data)))
    print('555555555555555555',data)
    
    return columns, data


    
    # chart = {'data':{'labels':[lst[0],lst[1]],'datasets':[{'values':[10,20]}]},'type':'bar'}

# STATIC REPORT
	# chart = {'data':{'labels':['d','o','g','s'],'datasets':[{'values':[3,6,4,7]}]},'type':'bar'}

	# report_summary = [
    # {"label":"Super","value":545,'indicator':'Red'},
    # {"label":"Duper","value":781,'indicator':'Blue'}]

	# chart = {
    # 'data':{
    #     'labels':['d','o','g','s'],
    #     'datasets':[
    #         {'name':'Number','values':[10,20,30,40]},
    #         {'name':'Vowel','values':[40,50,35,25]}
    #     ]
    # },
    # 'type':'bar'}

# 	chart = {
#     'data':{
#         'labels':['d','o','g','s'],
#         'datasets':[
#             #In axis-mixed charts you have to list the bar type first
#             {'name':'Number','values':[3,6,4,7],'chartType':'bar'},
#             {'name':'Vowel','values':[0,1,0,0],'chartType':'line'}
#         ]
#     },
#     'type':'axis-mixed'
# }	
#  	grid 
# 	columns = [
#     {'fieldname':'letter','label':'Letter','fieldtype':'Data','align':'right','width':200},
#     {'fieldname':'number','label':'Number','fieldtype':'Int','align':'right','width':200}
# ]

# 	tree

# 	columns = [
# 	{'fieldname':'letter','label':'Letter','fieldtype':'Data','dropdown':False,'sortable':False},
# 	{'fieldname':'number','label':'Number','fieldtype':'Int','dropdown':False,'sortable':False}
# ]

# 	data = [
# 		{'letter':'c','number':2,'indent':0},
# 		{'letter':'a','number':2,'indent':1},
# 		{'letter':'t','number':8,'indent':2},
# 		{'letter':'s','number':7,'indent':0}
# 	]
# 	

    



	# columns, data = ["Name","Centuries","Half Centuries","Level"], [['Vaibhav',112,220,'Legend'],['Rohit',20,40,'Beginner'],['Warner',45,40,'Pro'],['ABD',70,155,'Pro']]
    # return columns, data
    