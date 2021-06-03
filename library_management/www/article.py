import frappe
import json

def get_context(context):
    context.membership = frappe.get_list("Article", filters={'status': 'Available'}, fields=["name", "image"])


