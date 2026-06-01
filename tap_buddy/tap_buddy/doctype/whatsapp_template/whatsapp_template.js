// Copyright (c) 2026, Nigam and contributors
// For license information, please see license.txt

frappe.ui.form.on("WhatsApp Template", {
    refresh: function(frm) {
        if (!frm.is_new() && frm.doc.message) {
            frm.add_custom_button(__("Preview Message"), function() {
                const preview = frappe.utils.escape_html(frm.doc.message || "");
                frappe.msgprint({
                    title: __("Template Preview"),
                    message: `<pre style="white-space: pre-wrap; font-family: sans-serif;">${preview}</pre>`
                });
            });
        }
        if (!frm.is_new() && frm.doc.glific_push_status === "Not Pushed") {
            frm.add_custom_button(__("Push to Glific"), function() {
                frappe.call({
                    method: "tap_buddy.services.glific_template_service.create_and_push_template",
                    args: {
                        template_name: frm.doc.template_name,
                        message: frm.doc.message,
                        language: frm.doc.language,
                        category: frm.doc.category,
                        glific_shortcode: frm.doc.glific_shortcode
                    },
                    freeze: true,
                    freeze_message: __("Pushing Template to Glific..."),
                    callback: function(r) {
                        if (r.message && r.message.status === "ok") {
                            frappe.msgprint({
                                title: __("Push Successful"),
                                indicator: "green",
                                message: r.message.message
                            });
                            frm.reload_doc();
                        } else if (r.message && r.message.error) {
                            frappe.msgprint({
                                title: __("Push Failed"),
                                indicator: "red",
                                message: r.message.error
                            });
                        }
                    }
                });
            }).addClass("btn-primary");
        }
    }
});
