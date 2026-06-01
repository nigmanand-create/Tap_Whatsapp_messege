// Copyright (c) 2026, Nigam and contributors
// For license information, please see license.txt

frappe.listview_settings['WhatsApp Template'] = {
	onload: function(listview) {
		listview.page.add_inner_button(__("Sync Templates from Glific"), function() {
			frappe.call({
				method: "tap_buddy.tap_buddy.doctype.whatsapp_template.whatsapp_template.sync_glific_templates",
				freeze: true,
				freeze_message: __("Syncing Approved Templates from Glific..."),
				callback: function(r) {
					if(r.message) {
						frappe.msgprint({
							title: __("Sync Complete"),
							indicator: "green",
							message: r.message.message
						});
						listview.refresh();
					}
				}
			});
		}).addClass("btn-primary");
	}
};
