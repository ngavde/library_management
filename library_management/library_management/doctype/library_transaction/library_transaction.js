// Copyright (c) 2022, Vtech Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Library Transaction', {
	refresh: function(frm) {
		// Primary action buttons
		if (frm.doc.docstatus === 1 && frm.doc.transaction_type === 'Issue' && frm.doc.status === 'Issued') {
			frm.add_custom_button(__('Create Return'), function() {
				create_return_transaction(frm);
			}, __('Actions'));
		}

		// Helper buttons for book selection
		if (frm.doc.article && frm.doc.transaction_type === 'Issue') {
			frm.add_custom_button(__('Show Available Books'), function() {
				show_available_books(frm);
			}, __('Book Selection'));
		}

		if (frm.doc.library_member && frm.doc.transaction_type === 'Return') {
			frm.add_custom_button(__('Member\'s Issued Books'), function() {
				show_member_books(frm);
			}, __('Book Selection'));
		}

		// Member information - always show when member is selected
		if (frm.doc.library_member) {
			frm.add_custom_button(__('View Member History'), function() {
				show_member_history(frm);
			}, __('Member Info'));

			// Show connection info
			frm.dashboard.add_comment(
				__('Member History: Click "View Member History" to see complete transaction history for this member'),
				'blue', true
			);
		}
	},

	setup: function(frm) {
		// Set up filters for the book field
		set_book_query_filters(frm);
	},

	article: function(frm) {
		// Clear book selection when article changes
		if (frm.doc.book) {
			frm.set_value('book', '');
		}

		// Refresh book field filters
		frm.refresh_field('book');
	},

	transaction_type: function(frm) {
		// Clear book selection when transaction type changes
		if (frm.doc.book) {
			frm.set_value('book', '');
		}

		// Refresh book field filters
		frm.refresh_field('book');
	},

	library_member: function(frm) {
		// Refresh book field filters for return transactions
		if (frm.doc.transaction_type === 'Return') {
			frm.refresh_field('book');
		}
	},

	book: function(frm) {
		// Auto-fill article if not selected but book is selected
		if (frm.doc.book && !frm.doc.article) {
			frappe.db.get_value('Book', frm.doc.book, ['article', 'copy_number'])
				.then(r => {
					if (r.message && r.message.article) {
						frm.set_value('article', r.message.article);
						// Also update the fetched fields
						frm.refresh_field('copy_number');
						frm.refresh_field('barcode');
					}
				});
		}
	},

	validate: function(frm) {
		// Validate that book belongs to article
		if (frm.doc.book && frm.doc.article) {
			return new Promise((resolve, reject) => {
				frappe.db.get_value('Book', frm.doc.book, 'article')
					.then(r => {
						if (r.message && r.message.article !== frm.doc.article) {
							frappe.throw(__('Selected book does not belong to the selected article'));
							reject();
						} else {
							resolve();
						}
					});
			});
		}
	},

	before_save: function(frm) {
		// Additional validations
		if (frm.doc.transaction_type === 'Return' && !frm.doc.library_member) {
			frappe.throw(__('Library member is required for return transactions'));
		}

		if (frm.doc.transaction_type === 'Issue' && !frm.doc.due_date) {
			// Set default due date if not set
			let due_date = frappe.datetime.add_days(frm.doc.date, 14);
			frm.set_value('due_date', due_date);
		}
	}
});

function set_book_query_filters(frm) {
	// Set dynamic query for book field based on article and transaction type
	frm.set_query('book', function() {
		let filters = {};

		// Always filter by article if selected
		if (frm.doc.article) {
			filters['article'] = frm.doc.article;
		}

		// For issue transactions, only show available books
		if (frm.doc.transaction_type === 'Issue') {
			filters['status'] = 'Available';
		}

		// For return transactions, filter by books issued to this member
		if (frm.doc.transaction_type === 'Return' && frm.doc.library_member) {
			// Use custom query to filter books issued to this member
			return {
				query: 'library_management.library_management.doctype.library_transaction.library_transaction.get_book_query',
				filters: {
					'article': frm.doc.article,
					'transaction_type': frm.doc.transaction_type,
					'library_member': frm.doc.library_member
				}
			};
		}

		return {
			filters: filters
		};
	});
}

function create_return_transaction(frm) {
	frappe.call({
		method: 'library_management.library_management.doctype.library_transaction.library_transaction.create_return_transaction',
		args: {
			issue_transaction: frm.doc.name
		},
		callback: function(r) {
			if (r.message) {
				// Open the return transaction in a new form
				frappe.set_route('Form', 'Library Transaction', r.message.name);
			}
		}
	});
}

function show_available_books(frm) {
	if (!frm.doc.article) {
		frappe.msgprint(__('Please select an article first'));
		return;
	}

	if (!frm.doc.library_member) {
		frappe.msgprint(__('Please select a library member first'));
		return;
	}

	frappe.call({
		method: 'library_management.library_management.doctype.library_transaction.library_transaction.get_available_books_for_member',
		args: {
			article: frm.doc.article,
			member: frm.doc.library_member
		},
		callback: function(r) {
			if (r.message && r.message.length > 0) {
				show_books_dialog(r.message, 'Available Books for Article: ' + frm.doc.article_title, function(selected_book) {
					frm.set_value('book', selected_book);
				});
			} else {
				frappe.msgprint(__('No available books found for this article'));
			}
		}
	});
}

function show_member_books(frm) {
	if (!frm.doc.library_member) {
		frappe.msgprint(__('Please select a library member first'));
		return;
	}

	frappe.call({
		method: 'library_management.library_management.doctype.library_transaction.library_transaction.get_member_issued_books_with_details',
		args: {
			member: frm.doc.library_member
		},
		callback: function(r) {
			if (r.message && r.message.length > 0) {
				show_books_dialog(r.message, 'Books Issued to ' + frm.doc.library_member, function(selected_book) {
					frm.set_value('book', selected_book);
					// Also set the article automatically
					let book_data = r.message.find(b => b.book === selected_book);
					if (book_data && book_data.article) {
						frm.set_value('article', book_data.article);
					}
				}, true);
			} else {
				frappe.msgprint(__('No books currently issued to this member'));
			}
		}
	});
}

function show_books_dialog(books, title, callback, include_article = false) {
	let d = new frappe.ui.Dialog({
		title: title,
		fields: [
			{
				fieldtype: 'HTML',
				fieldname: 'books_html'
			}
		],
		primary_action_label: __('Select'),
		primary_action: function() {
			let selected = d.$wrapper.find('input[name="book_select"]:checked').val();
			if (selected) {
				callback(selected);
				d.hide();
			} else {
				frappe.msgprint(__('Please select a book'));
			}
		}
	});

	// Build HTML table
	let html = '<table class="table table-bordered table-striped"><thead><tr>';
	html += '<th width="10%">Select</th><th>Copy #</th><th>Barcode</th><th>Status</th>';
	if (include_article) {
		html += '<th>Article</th><th>Due Date</th><th>Status</th>';
	} else {
		html += '<th>Condition</th><th>Location</th>';
	}
	html += '</tr></thead><tbody>';

	books.forEach(function(book) {
		html += '<tr>';
		html += `<td><input type="radio" name="book_select" value="${book.name || book.book}"></td>`;
		html += `<td>${book.copy_number || ''}</td>`;
		html += `<td>${book.barcode || ''}</td>`;
		// Handle both book status and transaction status
		let book_status = book.status || book.book_status || '';
		if (book_status === 'Reserved') {
			html += `<td><span class="indicator orange">Reserved (for you)</span></td>`;
		} else {
			html += `<td><span class="indicator ${get_status_color(book_status)}">${book_status}</span></td>`;
		}

		if (include_article) {
			html += `<td>${book.article_title || ''}</td>`;
			html += `<td>${book.due_date ? frappe.datetime.str_to_user(book.due_date) : ''}</td>`;
			html += `<td>${book.book_status === 'Overdue' ? '<span class="text-danger">Overdue</span>' : 'Active'}</td>`;
		} else {
			html += `<td>${book.condition || ''}</td>`;
			html += `<td>${book.location || ''}</td>`;
		}
		html += '</tr>';
	});

	html += '</tbody></table>';

	if (books.length === 0) {
		html = '<p class="text-muted">No books found.</p>';
	}

	d.fields_dict.books_html.$wrapper.html(html);
	d.show();
}

function get_status_color(status) {
	const status_colors = {
		'Available': 'green',
		'Issued': 'orange',
		'Reserved': 'orange',
		'Maintenance': 'yellow',
		'Lost': 'red',
		'Damaged': 'red',
		'Overdue': 'red',
		'Active': 'blue'
	};
	return status_colors[status] || 'gray';
}

function show_member_history(frm) {
	if (!frm.doc.library_member) {
		frappe.msgprint(__('Please select a library member first'));
		return;
	}

	// Show loading message
	frappe.show_alert(__('Loading member history...'), 3);

	// Check if history exists
	frappe.db.get_value('Library Member History', {'member_name': frm.doc.library_member}, 'name')
		.then(r => {
			if (r.message && r.message.name) {
				// History exists, open it
				frappe.show_alert(__('Opening member history record...'), 2);
				frappe.set_route('Form', 'Library Member History', r.message.name);
			} else {
				// No history exists, inform user
				frappe.msgprint({
					title: __('Member History'),
					message: __('No transaction history found for this member. History will be created automatically when this transaction is submitted.'),
					indicator: 'blue'
				});
			}
		})
		.catch(err => {
			frappe.msgprint({
				title: __('Error'),
				message: __('Could not load member history. Please try again.'),
				indicator: 'red'
			});
		});
}