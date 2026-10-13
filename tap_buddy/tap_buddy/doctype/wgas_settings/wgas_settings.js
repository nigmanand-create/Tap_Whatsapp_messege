frappe.ui.form.on("WGAS Settings", {
	onload(frm) {
		tap_buddy.wgas.ensure_css();
		if (!frm.doc.glific_url && !frm.wgas_tbs_load_done) {
			frm.wgas_tbs_load_done = true;
			frappe.call({
				method: "tap_buddy.tap_buddy.doctype.wgas_settings.wgas_settings.load_from_tap_buddy",
				freeze: false,
				callback(r) {
					if (!r.exc && r.message && r.message.status === "success") {
						frm.reload_doc();
					}
				},
			});
		}
	},

	refresh(frm) {
		tap_buddy.wgas.ensure_css();
		if (!frm.wgas_sync_zone_ready) {
			frm.wgas_sync_zone_ready = true;
			const $layout = $(frm.wrapper).find(".form-layout").first();
			$layout.addClass("wgas-sync-zone");
			if (!$layout.find(".wgas-sync-status").length) {
				$layout.prepend('<span class="wgas-sync-status"></span>');
			}
		}

		refresh_wgas_status(frm, false);

		frm.add_custom_button(__("Verify connection"), () => refresh_wgas_status(frm, true), __("Actions"));

		frm.add_custom_button(
			__("Bootstrap login"),
			() => {
				const d = new frappe.ui.Dialog({
					title: __("Glific login"),
					fields: [
						{
							fieldtype: "Data",
							fieldname: "phone",
							label: __("Phone"),
							default: frm.doc.glific_phone_number,
							reqd: 1,
						},
						{ fieldtype: "Password", fieldname: "password", label: __("Password"), reqd: 1 },
					],
					primary_action_label: __("Sign in & store tokens"),
					primary_action(values) {
						if (values.phone !== frm.doc.glific_phone_number) {
							frm.set_value("glific_phone_number", values.phone);
						}
						frm.save().then(() => {
							frappe.call({
								method: "tap_buddy.tap_buddy.doctype.wgas_settings.wgas_settings.bootstrap_glific",
								args: { password: values.password },
								freeze: true,
								callback(r) {
									d.hide();
									const msg = r.message || {};
									frappe.show_alert({
										message: msg.message || __("Login complete"),
										indicator: msg.status === "success" ? "green" : "red",
									});
									frm.reload_doc();
								},
							});
						});
					},
				});
				d.show();
			},
			__("Actions")
		);

		frm.add_custom_button(__("Sync WhatsApp groups"), () => {
			const $zone = $(frm.wrapper).find(".form-layout").first();
			tap_buddy.wgas.run_paginated_sync({
				phases: ["collections", "wa_groups"],
				$zone,
				on_done: () => frm.reload_doc(),
			});
		}, __("Actions"));
		frm.add_custom_button(__("Sync Glific flows"), () => {
			const $zone = $(frm.wrapper).find(".form-layout").first();
			tap_buddy.wgas.run_paginated_sync({
				phases: ["flows"],
				$zone,
				on_done: () => frm.reload_doc(),
			});
		}, __("Actions"));
		frm.add_custom_button(
			__("Open control center"),
			() => frappe.set_route("wgas-hub"),
			__("Navigate")
		);

		frm.set_df_property("section_advanced", "collapsible", 1);
	},
});

function _wgas_indicator_color(status) {
	const map = {
		Connected: "green",
		Failed: "red",
		"Not Configured": "orange",
		"Not Tested": "grey",
	};
	return map[status] || "grey";
}

function refresh_wgas_status(frm, live) {
	const method = live
		? "tap_buddy.tap_buddy.doctype.wgas_settings.wgas_settings.refresh_connection_status"
		: "tap_buddy.tap_buddy.doctype.wgas_settings.wgas_settings.get_connection_status";

	frappe.call({
		method,
		freeze: false,
		callback(r) {
			if (!r.message) return;
			const data = r.message;
			frm.set_value("glific_connection_status", data.glific_status || "Not Tested");
			frm.set_value("glific_last_tested_at", data.last_tested_at || null);
			frm.set_value("glific_connection_message", data.message || "");

			const status = data.glific_status || "Not Tested";
			let banner_class = "is-warn";
			if (status === "Connected") banner_class = "is-connected";
			if (status === "Failed") banner_class = "is-failed";

			const cred = data.has_credentials ? __("Credentials on file") : __("Credentials missing");
			const wh =
				data.webhook_enabled && data.has_webhook_secret
					? __("Webhooks configured")
					: data.webhook_enabled
						? __("Webhooks enabled — add secret")
						: __("Webhooks off");

			frm.set_intro("");
			if (frm.dashboard) {
				frm.dashboard.reset();
				frm.dashboard.add_indicator(__("Glific"), status, _wgas_indicator_color(status));
				frm.dashboard.add_indicator(
					__("Auth"),
					data.has_credentials ? __("OK") : __("Required"),
					data.has_credentials ? "green" : "orange"
				);
				frm.dashboard.add_indicator(
					__("Webhooks"),
					data.webhook_enabled ? __("On") : __("Off"),
					data.webhook_enabled ? "blue" : "grey"
				);
			}

			$(frm.wrapper)
				.find(".wgas-settings-banner")
				.remove();
			$(frm.wrapper)
				.find(".form-layout")
				.first()
				.prepend(
					`<div class="wgas-form-banner wgas-settings-banner ${banner_class}">
						<strong>${frappe.utils.escape_html(status)}</strong>
						— ${frappe.utils.escape_html(data.message || "")}
						<span style="opacity:0.85"> · ${cred} · ${wh}</span>
					</div>`
				);
		},
	});
}
