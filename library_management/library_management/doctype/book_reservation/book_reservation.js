// Copyright (c) 2023, Vtech Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Book Reservation', {
	refresh: function(frm) {
		// Add button to fulfill reservation (issue book)
		if (frm.doc.docstatus === 1 && frm.doc.status === 'Active' && frm.doc.selected_book) {
			frm.add_custom_button(__('Fulfill Reservation (Issue Book)'), function() {
				fulfill_reservation(frm);
			}, __('Actions'));
		}

		// Add button to create return transaction for fulfilled reservations
		if (frm.doc.docstatus === 1 && frm.doc.status === 'Fulfilled' && frm.doc.selected_book) {
			frm.add_custom_button(__('Create Return Transaction'), function() {
				create_return_from_reservation(frm);
			}, __('Actions'));
		}

		// Add button to cancel reservation
		if (frm.doc.docstatus === 1 && frm.doc.status === 'Active') {
			frm.add_custom_button(__('Cancel Reservation'), function() {
				cancel_reservation(frm);
			}, __('Actions'));
		}

		// Show reservation queue position
		if (frm.doc.article && frm.doc.status === 'Active') {
			frappe.call({
				method: 'library_management.library_management.doctype.book_reservation.book_reservation.get_reservation_queue',
				args: {
					article: frm.doc.article
				},
				callback: function(r) {
					if (r.message && r.message.length > 0) {
						let position = r.message.findIndex(res => res.name === frm.doc.name) + 1;
						if (position > 0) {
							frm.dashboard.add_comment(
								__('Queue Position: {0} of {1} active reservations', [position, r.message.length]),
								'blue', true
							);
						}
					}
				}
			});
		}

		// Show workflow status for submitted reservations
		if (frm.doc.docstatus === 1 && frm.doc.name) {
			show_workflow_status(frm);
		}
	},

	setup: function(frm) {
		// Set up query filter for selected_book field
		frm.set_query('selected_book', function() {
			if (frm.doc.article) {
				return {
					filters: {
						'article': frm.doc.article,
						'status': 'Available'
					}
				};
			} else {
				return {
					filters: {
						'name': 'none'  // Show no results if no article selected
					}
				};
			}
		});
	},

	article: function(frm) {
		// Clear selected book when article changes
		if (frm.doc.selected_book) {
			frm.set_value('selected_book', '');
		}
		// Refresh available books list and book field
		frm.refresh_field('available_books_list');
		frm.refresh_field('selected_book');
	}
});

function fulfill_reservation(frm) {
	frappe.confirm(
		__('Are you sure you want to fulfill this reservation? This will issue the book to the member.'),
		function() {
			frappe.call({
				method: 'fulfill_reservation',
				doc: frm.doc,
				callback: function(r) {
					if (r.message) {
						frappe.show_alert(__('Reservation fulfilled successfully'), 5);
						frm.reload_doc();
					}
				}
			});
		}
	);
}

function create_return_from_reservation(frm) {
	frappe.confirm(
		__('Create a return transaction for the book issued from this reservation?'),
		function() {
			frappe.call({
				method: 'create_return_from_reservation',
				doc: frm.doc,
				callback: function(r) {
					if (r.message) {
						frappe.show_alert(__('Return transaction created successfully'), 5);

						// Route to the new return transaction
						if (r.message.return_transaction) {
							frappe.set_route('Form', 'Library Transaction', r.message.return_transaction);
						}
					}
				}
			});
		}
	);
}

function cancel_reservation(frm) {
	frappe.prompt([
		{
			fieldname: 'reason',
			fieldtype: 'Text',
			label: __('Cancellation Reason'),
			reqd: 1
		}
	],
	function(data) {
		frappe.call({
			method: 'cancel_reservation',
			doc: frm.doc,
			args: {
				reason: data.reason
			},
			callback: function(r) {
				frappe.show_alert(__('Reservation cancelled successfully'), 5);
				frm.reload_doc();
			}
		});
	},
	__('Cancel Reservation'),
	__('Cancel')
	);
}

function show_workflow_status(frm) {
	frappe.call({
		method: 'library_management.library_management.doctype.book_reservation.book_reservation.get_reservation_workflow_status',
		args: {
			reservation_name: frm.doc.name
		},
		callback: function(r) {
			if (r.message) {
				let status = r.message;
				let workflow_info = [];

				// Build workflow status display
				workflow_info.push(__('📋 Reservation: {0}', [status.reservation_status]));

				if (status.selected_book) {
					workflow_info.push(__('📖 Book: {0} (Status: {1})', [status.selected_book, status.book_status || 'Unknown']));
				}

				if (status.issue_transaction) {
					workflow_info.push(__('📤 Issued: Transaction {0} ({1})', [status.issue_transaction.name, status.issue_transaction.status]));
				}

				if (status.return_transaction) {
					workflow_info.push(__('📥 Returned: Transaction {0} ({1})', [status.return_transaction.name, status.return_transaction.status]));
				}

				// Show complete workflow status
				if (workflow_info.length > 1) {
					frm.dashboard.add_comment(
						__('Workflow Status: ') + workflow_info.join(' → '),
						status.return_transaction ? 'green' : (status.issue_transaction ? 'orange' : 'blue'),
						true
					);
				}
			}
		}
	});
}