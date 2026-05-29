// Copyright (c) 2026, Nigam and contributors
// For license information, please see license.txt

frappe.ui.form.on("TAP Buddy Settings", {
	refresh(frm) {
		frm.add_custom_button(__("Bootstrap Glific Credentials"), function() {
			let dialog = new frappe.ui.Dialog({
				title: __("Bootstrap Glific Credentials"),
				fields: [
					{
						label: __("Phone Number"),
						fieldname: "phone",
						fieldtype: "Data",
						reqd: 1
					},
					{
						label: __("Password"),
						fieldname: "password",
						fieldtype: "Password",
						reqd: 1
					}
				],
				primary_action_label: __("Authenticate"),
				primary_action: function(values) {
					frappe.call({
						method: "tap_buddy.tap_buddy.doctype.tap_buddy_settings.tap_buddy_settings.bootstrap_glific_session",
						args: {
							phone: values.phone,
							password: values.password
						},
						freeze: true,
						freeze_message: __("Authenticating with Glific..."),
						callback: function(r) {
							if(r.message) {
								if(r.message.status === "success") {
									frappe.msgprint({title: __("Success"), indicator: "green", message: r.message.message});
									dialog.hide();
									frm.reload_doc();
								} else {
									frappe.msgprint({title: __("Error"), indicator: "red", message: r.message.message});
								}
							}
						}
					});
				}
			});
			dialog.show();
		}).addClass("btn-primary");

		frm.add_custom_button(__("Test Connection"), function() {
			frappe.call({
				method: "tap_buddy.tap_buddy.doctype.tap_buddy_settings.tap_buddy_settings.test_glific_connection",
				freeze: true,
				freeze_message: __("Testing Connection..."),
				callback: function(r) {
					if(r.message) {
						if(r.message.status === "success") {
							frappe.msgprint({title: __("Connected"), indicator: "green", message: r.message.message});
						} else {
							frappe.msgprint({title: __("Failed"), indicator: "red", message: r.message.message});
						}
					}
				}
			});
		});

		frappe.call({
			method: "tap_buddy.tap_buddy.doctype.tap_buddy_settings.tap_buddy_settings.get_auth_dashboard_metrics",
			callback: function(r) {
				if(r.message) {
					let data = r.message;
					let color_map = {
						"Green": "green",
						"Yellow": "orange",
						"Red": "red"
					};
					let color = color_map[data.severity] || "blue";
					
					let html = `<div class="row">
						<div class="col-md-3"><b>Status:</b> <span style="color: ${color}; font-weight: bold;">${data.status}</span></div>
						<div class="col-md-3"><b>Expiry in:</b> ${data.mins_to_expiry !== null ? data.mins_to_expiry + ' mins' : 'N/A'}</div>
						<div class="col-md-3"><b>Last Refresh:</b> ${data.last_refresh_time || 'Never'}</div>
						<div class="col-md-3"><b>Refresh Token:</b> ${data.has_refresh_token ? '✅ Present' : '❌ Missing'}</div>
					</div>`;
					
					if (data.last_error) {
						html += `<div class="row mt-2"><div class="col-md-12 text-danger"><b>Last Error:</b> ${data.last_error}</div></div>`;
					}
					
					frm.dashboard.set_headline(html);
				}
			}
		});
	},
});
