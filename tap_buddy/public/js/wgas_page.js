frappe.provide("tap_buddy.wgas");

tap_buddy.wgas.ensure_css = function () {
	if (document.getElementById("wgas-desk-css")) return;
	const link = document.createElement("link");
	link.id = "wgas-desk-css";
	link.rel = "stylesheet";
	link.href = "/assets/tap_buddy/css/wgas.css";
	document.head.appendChild(link);
};

tap_buddy.wgas.status_pill_class = function (status) {
	const map = {
		Connected: "wgas-pill--green",
		Failed: "wgas-pill--red",
		"Not Configured": "wgas-pill--orange",
		"Not Tested": "wgas-pill--grey",
		Active: "wgas-pill--blue",
		Completed: "wgas-pill--green",
		Draft: "wgas-pill--grey",
		Imported: "wgas-pill--blue",
		Scheduling: "wgas-pill--orange",
	};
	return map[status] || "wgas-pill--grey";
};

tap_buddy.wgas.plan_status_pill = function (status) {
	const cls = tap_buddy.wgas.status_pill_class(status);
	return `<span class="wgas-pill ${cls}">${frappe.utils.escape_html(status || "—")}</span>`;
};

tap_buddy.wgas.set_sync_loading = function ($zone, on, statusText) {
	if (!$zone || !$zone.length) return;
	if (on) {
		$zone.addClass("is-loading");
		$zone.find(".wgas-sync-status").text(statusText || __("Syncing…"));
	} else {
		$zone.removeClass("is-loading");
		$zone.find(".wgas-sync-status").text("");
	}
};

/**
 * Progressive Glific sync — many small API calls, freeze: false, local overlay only.
 * @param {object} opts
 * @param {string[]} opts.phases — collections | wa_groups | flows
 * @param {jQuery} opts.$zone — element with .wgas-sync-zone
 * @param {function} [opts.on_done]
 * @param {function} [opts.on_error]
 */
tap_buddy.wgas.run_paginated_sync = function (opts) {
	const phases = opts.phases || ["collections", "wa_groups"];
	const $zone = opts.$zone;
	let phase_index = 0;
	let page = 1;
	const page_size = opts.page_size || 50;

	function run_step() {
		if (phase_index >= phases.length) {
			tap_buddy.wgas.set_sync_loading($zone, false);
			frappe.show_alert({ message: __("Sync complete"), indicator: "green" });
			if (opts.on_done) opts.on_done();
			return;
		}

		const phase = phases[phase_index];
		frappe.call({
			method: "tap_buddy.wgas.glific_sync_batches.sync_glific_batch",
			args: { phase, page, page_size },
			freeze: false,
			callback(r) {
				const m = r.message || {};
				if (m.error || r.exc) {
					tap_buddy.wgas.set_sync_loading($zone, false);
					frappe.msgprint({
						title: __("Sync failed"),
						message: m.error || r.exc,
						indicator: "red",
					});
					if (opts.on_error) opts.on_error(m);
					return;
				}
				tap_buddy.wgas.set_sync_loading($zone, true, m.message || __("Syncing…"));
				if (m.has_more && m.next_page) {
					page = m.next_page;
					run_step();
				} else {
					phase_index += 1;
					page = 1;
					run_step();
				}
			},
		});
	}

	tap_buddy.wgas.set_sync_loading($zone, true, __("Starting sync…"));
	run_step();
};
