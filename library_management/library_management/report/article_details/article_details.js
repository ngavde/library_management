
// Copyright (c) 2016, Dexciss and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Article Details"] = {
	"filters": [
        {
			"fieldname":"article",
			"label": __("Article"),
			"fieldtype": "Link",
			"options": "Article"
		}
	]
};
