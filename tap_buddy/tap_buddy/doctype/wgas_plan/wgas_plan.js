frappe.ui.form.on("WGAS Plan", {
	refresh(frm) {
		tap_buddy.wgas.ensure_css();

		if (frm.is_new()) {
			frm.set_intro(__("Step 1: Name your plan and attach the monthly Excel file."), "blue");
			return;
		}

		const step = _wgas_workflow_step(frm);
		const intros = {
			1: __("Step 2: Import Excel to build the schedule grid."),
			2: __("Step 3: Review rows, then publish scheduled campaigns."),
			3: __("Step 4: Monitor sends and refresh engagement after run times."),
		};
		frm.set_intro(intros[step] || intros[3], step === 3 ? "green" : "blue");

		if (frm.dashboard) {
			frm.dashboard.reset();
			frm.dashboard.add_indicator(__("Items"), String(frm.doc.total_items || 0), "blue");
			frm.dashboard.add_indicator(__("Scheduled"), String(frm.doc.scheduled_items || 0), "orange");
			frm.dashboard.add_indicator(__("Completed"), String(frm.doc.completed_items || 0), "green");
			if (frm.doc.failed_items) {
				frm.dashboard.add_indicator(__("Failed"), String(frm.doc.failed_items), "red");
			}
		}

		if (!frm.doc.excel_file) {
			frm.set_df_property("excel_file", "description", __("Columns: date, time, groups, message, flow"));
		}

		if (frm.doc.excel_file && (!frm.doc.items || !frm.doc.items.length)) {
			frm.add_custom_button(__("Import Excel"), () => _import_excel(frm), __("Workflow"));
		} else if (frm.doc.items && frm.doc.items.length) {
			frm.add_custom_button(__("Re-import Excel"), () => _import_excel(frm), __("Workflow"));
			if ((frm.doc.scheduled_items || 0) < (frm.doc.total_items || 0)) {
				frm.add_custom_button(__("Publish schedule"), () => _publish(frm), __("Workflow")).addClass(
					"btn-primary"
				);
			}
			frm.add_custom_button(__("Refresh engagement"), () => _engagement(frm), __("Workflow"));
		}

		frm.add_custom_button(__("WGAS home"), () => frappe.set_route("wgas-hub"), __("Navigate"));
	},

	excel_file(frm) {
		if (frm.doc.excel_file && frm.is_new()) {
			frm.set_intro(__("Save the plan, then use Import Excel."), "blue");
		}
	},
});

function _wgas_workflow_step(frm) {
	if (!frm.doc.items || !frm.doc.items.length) return 1;
	if ((frm.doc.scheduled_items || 0) < (frm.doc.total_items || 0)) return 2;
	return 3;
}

function _import_excel(frm) {
	if (!frm.doc.excel_file) {
		frappe.msgprint(__("Attach an Excel file first."));
		return;
	}
	frm.call("import_from_excel").then((r) => {
		frappe.show_alert({ message: r.message || __("Imported"), indicator: "green" });
		frm.reload_doc();
	});
}

function _publish(frm) {
	frappe.confirm(__("Create scheduled TAP Campaigns for every row?"), () => {
		frm.call("build_schedule").then((r) => {
			frappe.show_alert({ message: r.message || __("Scheduled"), indicator: "green" });
			frm.reload_doc();
		});
	});
}

function _engagement(frm) {
	frm.call("refresh_engagement").then((r) => {
		frappe.show_alert({ message: r.message || __("Updated"), indicator: "green" });
		frm.reload_doc();
	});
}
