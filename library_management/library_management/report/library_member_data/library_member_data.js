// Copyright (c) 2022, Vtech Technologies and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Library Member Data"] = {
	"filters": [
		{
			fieldname: "from_date",
			label: "From Date",
			fieldtype: "Date",
			default: frappe.datetime.get_today()
		},

		{
		fieldname: "to_date",
		label: "To Date",
		fieldtype: "Date",
		default: frappe.datetime.get_today()

	},
	{
		fieldname:"article",
		label:"Article",
		fieldtype:"Link",
		options:"Article_New"

	},
{
	fieldname:"status",
		label:"Status",
		fieldtype:"Select",
		options:"Issued\nReturned"

},
{
	fieldname:"first_name",
		label:"Member Name",
		fieldtype:"Link",
		options:"Library Member"

}
	
		
		
			
	]
};
