# Copyright (c) 2013, Dexciss and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _, _dict
from frappe.utils.dateutils import get_dates_from_timegrain
from datetime import datetime

def execute(filters=None):
    columns, data = [], []
    columns = get_columns(filters)
    data = get_result(filters)
    return columns, data

def get_result(filters=None):
    query = """ select name,
                case when status = %s Then 1 else 0 end as available_qty,
                case when status = "xyz" Then 1 else 1 end as total_qty
                from `tabArticle`
                """
    if filters:
        cond = get_conditions(filters)
        query += cond

    res = frappe.db.sql(query,("Available"))
    return res

def get_columns(filters):
    columns = [
        {
            "fieldname": "article",
            "label": _("Article"),
            "fieldtype": "Link",
            "options": "Article",
            "width": 120
        },
        {
            "fieldname": "available_qty",
            "label": _("Available Qty"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "total_qty",
            "label": _("Total QTY"),
            "fieldtype": "Data",
            "width": 120,
			"default": 1
        }
    ]
    return columns

def get_conditions(filters):
    query = """ """
    if filters:
        if filters.get('article'):
            query += """ where name = '%s'  """%filters.article
    return query


