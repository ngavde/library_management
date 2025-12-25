// Copyright (c) 2022, Vtech Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Library Transaction', {
	refresh: function(frm) {
		
			
		frm.add_custom_button(__('See history'), function(){
			// frappe.set_route("Form", "Library Member History", "LMHistory-0002")
			frappe.new_doc("Library Member History",{"member_name":frm.doc.library_membe})
			
		}, __("Click"));

		

	},

	// setup: function(frm){
	// 	frm.set_query("library_membe", function() {
			
	// 		return {
	// 			   filters: [['check','=', '1']
	// 			   ]};
	// 	});

					 
	// },	

	setup: function(frm){
			

		frm.set_query("article", function() {

			if(frm.doc.returned == 1)	{
			return {
				   filters: [['status','=','Issued']
				   ]};}
			else {
				return{
					filters:[['status','=','Available']]
				}
			}
		});
						 
		},	

	

	
	
	validate: function(frm){
		let stat_us = frm.doc.type

		if (stat_us == 'Issued' && frm.doc.returned == 0) {
			frappe.throw('Sorry, Article is not availaible.')
		}
	},

	

	before_save: function(frm){
		let stat_us = frm.doc.type

		if (stat_us == 'Available') {
			frappe.msgprint('Article is available.')
			
		}

	


	

	

	
	},

	before_save: function(frm){
		let s = frm.doc.type
		let r = frm.doc.returned
		if (s == 'Available' && r == 1) {
			frappe.throw("'Available' book cannot be returned.")
			
		}
		

	}
	

	
		
	

	


});
