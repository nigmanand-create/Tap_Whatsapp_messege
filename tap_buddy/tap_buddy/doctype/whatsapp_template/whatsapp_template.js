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
    }
});
