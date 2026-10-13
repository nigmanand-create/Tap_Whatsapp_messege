frappe.pages["wgas-hub"].on_page_load = function (wrapper) {
	tap_buddy.wgas.ensure_css();
	new WGASControlCenter(wrapper);
};

class WGASControlCenter {
	constructor(wrapper) {
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("WGAS"),
			single_column: true,
		});

		this.$shell = $('<div class="wgas-shell"></div>').appendTo(this.page.main);

		this.page.set_primary_action(__("New monthly plan"), () => frappe.new_doc("WGAS Plan"), "add");
		this.page.add_inner_button(__("Settings"), () => frappe.set_route("Form", "WGAS Settings", "WGAS Settings"));
		this.page.add_inner_button(__("Refresh"), () => this.load(), "reload");

		this.load();
	}

	load() {
		frappe.call({
			method: "tap_buddy.api.wgas.dashboard",
			freeze: false,
			callback: (r) => this.render(r.message || {}),
		});
	}

	render(data) {
		const conn = data.connection || {};
		const counts = data.counts || {};
		const glific = conn.glific_status || "Not Tested";
		const glific_cls = tap_buddy.wgas.status_pill_class(glific);

		const cred_label = conn.has_credentials ? __("Configured") : __("Not set");
		const cred_cls = conn.has_credentials ? "wgas-pill--green" : "wgas-pill--orange";

		const wh_label =
			conn.webhook_enabled && conn.has_webhook_secret
				? __("Ready")
				: conn.webhook_enabled
					? __("Secret missing")
					: __("Disabled");
		const wh_cls =
			conn.webhook_enabled && conn.has_webhook_secret
				? "wgas-pill--green"
				: conn.webhook_enabled
					? "wgas-pill--orange"
					: "wgas-pill--grey";

		this.$shell.html(`
			<div class="wgas-hero">
				<h1>${frappe.utils.escape_html(data.system || "WGAS")}</h1>
				<p>${__("Upload Excel → schedule group messages & flows → track delivery and responses.")}</p>
			</div>

			<div class="wgas-grid">
				<div class="wgas-card">
					<div class="wgas-card-label">${__("Glific API")}</div>
					<div class="wgas-card-value"><span class="wgas-pill ${glific_cls}">${frappe.utils.escape_html(glific)}</span></div>
					<div class="wgas-card-meta">${frappe.utils.escape_html(conn.message || __("Run connection test in Settings"))}</div>
				</div>
				<div class="wgas-card">
					<div class="wgas-card-label">${__("Credentials")}</div>
					<div class="wgas-card-value"><span class="wgas-pill ${cred_cls}">${cred_label}</span></div>
					<div class="wgas-card-meta">${__("Bootstrap login in WGAS Settings")}</div>
				</div>
				<div class="wgas-card">
					<div class="wgas-card-label">${__("Webhooks")}</div>
					<div class="wgas-card-value"><span class="wgas-pill ${wh_cls}">${wh_label}</span></div>
					<div class="wgas-card-meta">${__("Delivery & read tracking")}</div>
				</div>
				<div class="wgas-card">
					<div class="wgas-card-label">${__("WhatsApp groups")}</div>
					<div class="wgas-card-value">${counts.whatsapp_groups || 0}</div>
					<div class="wgas-card-meta">${__("Synced from Glific")}</div>
				</div>
				<div class="wgas-card">
					<div class="wgas-card-label">${__("Glific flows")}</div>
					<div class="wgas-card-value">${counts.glific_flows || 0}</div>
					<div class="wgas-card-meta">${__("Available for Excel column")}</div>
				</div>
				<div class="wgas-card">
					<div class="wgas-card-label">${__("Active plans")}</div>
					<div class="wgas-card-value">${counts.plans_active || 0}</div>
					<div class="wgas-card-meta">${__("Of {0} total", [counts.plans_total || 0])}</div>
				</div>
			</div>

			<div class="wgas-actions wgas-sync-zone" data-wgas-sync-zone="1">
				<button type="button" class="btn btn-primary btn-sm" data-action="new-plan">${__("New plan")}</button>
				<button type="button" class="btn btn-default btn-sm" data-action="settings">${__("Connection settings")}</button>
				<button type="button" class="btn btn-default btn-sm" data-action="sync-groups">${__("Sync groups")}</button>
				<button type="button" class="btn btn-default btn-sm" data-action="sync-flows">${__("Sync flows")}</button>
				<button type="button" class="btn btn-default btn-sm" data-action="test">${__("Test Glific")}</button>
				<span class="wgas-sync-status"></span>
			</div>

			<div class="wgas-panel">
				<div class="wgas-panel-head">
					<h2>${__("Monthly plans")}</h2>
				</div>
				<div class="wgas-panel-body"></div>
			</div>
		`);

		this.$shell.find('[data-action="new-plan"]').on("click", () => frappe.new_doc("WGAS Plan"));
		this.$shell.find('[data-action="settings"]').on("click", () =>
			frappe.set_route("Form", "WGAS Settings", "WGAS Settings")
		);
		this.$shell.find('[data-action="sync-groups"]').on("click", () => {
			const $zone = this.$shell.find('[data-wgas-sync-zone="1"]');
			tap_buddy.wgas.run_paginated_sync({
				phases: ["collections", "wa_groups"],
				$zone,
				on_done: () => this.load(),
			});
		});
		this.$shell.find('[data-action="sync-flows"]').on("click", () => {
			const $zone = this.$shell.find('[data-wgas-sync-zone="1"]');
			tap_buddy.wgas.run_paginated_sync({
				phases: ["flows"],
				$zone,
				on_done: () => this.load(),
			});
		});
		this.$shell.find('[data-action="test"]').on("click", () => this._run("test_glific_connection", true));

		this._render_plans(data.plans || []);
	}

	_run(method, reload_after) {
		frappe.call({
			method: `tap_buddy.tap_buddy.doctype.wgas_settings.wgas_settings.${method}`,
			freeze: false,
			callback: (r) => {
				const msg = (r.message && r.message.message) || r.message;
				frappe.show_alert({ message: msg || __("Done"), indicator: "green" });
				if (reload_after) this.load();
			},
		});
	}

	_render_plans(plans) {
		const $body = this.$shell.find(".wgas-panel-body");
		if (!plans.length) {
			$body.html(`
				<div class="wgas-empty">
					<p>${__("No plans yet.")}</p>
					<button type="button" class="btn btn-primary btn-sm" data-action="new-plan-empty">${__("Create your first plan")}</button>
				</div>
			`);
			$body.find('[data-action="new-plan-empty"]').on("click", () => frappe.new_doc("WGAS Plan"));
			return;
		}

		const rows = plans
			.map(
				(p) => `
			<tr>
				<td><a href="/app/wgas-plan/${encodeURIComponent(p.name)}">${frappe.utils.escape_html(p.plan_title || p.name)}</a></td>
				<td>${tap_buddy.wgas.plan_status_pill(p.status)}</td>
				<td>${p.total_items || 0}</td>
				<td>${p.scheduled_items || 0}</td>
				<td>${p.completed_items || 0}</td>
				<td>${p.failed_items || 0}</td>
			</tr>`
			)
			.join("");

		$body.html(`
			<table class="wgas-table">
				<thead>
					<tr>
						<th>${__("Plan")}</th>
						<th>${__("Status")}</th>
						<th>${__("Items")}</th>
						<th>${__("Scheduled")}</th>
						<th>${__("Done")}</th>
						<th>${__("Failed")}</th>
					</tr>
				</thead>
				<tbody>${rows}</tbody>
			</table>
		`);
	}
}
