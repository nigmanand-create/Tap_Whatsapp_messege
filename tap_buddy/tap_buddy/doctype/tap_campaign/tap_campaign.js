frappe.ui.form.on("TAP Campaign", {
	refresh(frm) {
		frm.__last_template_message = frm.doc.template
			? frm.doc.message_template || ""
			: frm.doc.message_template || "";

		if (frm.doc.docstatus === 1 && frm.doc.status) {
			frm.refresh_field("status");
		}
	},

	before_submit(frm) {
		frm.set_value("status", "Queued");
		frm.refresh_field("status");
	},

	after_submit(frm) {
		frm.reload_doc();
	},

	template(frm) {
		if (!frm.doc.template) {
			frm.set_value("message_template", "");
			frm.__last_template_message = "";
			return;
		}

		frappe.db
			.get_value("WhatsApp Template", frm.doc.template, ["message"])
			.then((r) => {
				const templateText = r.message?.message || "";
				const currentMessage = (frm.doc.message_template || "").trim();
				const previousTemplateMessage = (frm.__last_template_message || "").trim();

				if (!currentMessage || currentMessage === previousTemplateMessage) {
					frm.set_value("message_template", templateText);
					frm.__last_template_message = templateText;
				}
			});
	},
});
