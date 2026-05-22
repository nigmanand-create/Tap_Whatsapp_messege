frappe.ui.form.on("TAP Campaign", {
    refresh: function(frm) {
        if (!frm.is_new() && frm.doc.template) {
            if (!frm.doc.__last_template_message && frm.doc.message_template) {
                frappe.db.get_doc("WhatsApp Template", frm.doc.template).then(doc => {
                    const template = doc.message || doc.message_body || "";
                    frm.doc.__last_template_message = clean_message(template);
                });
            }
            frm.add_custom_button(__('Preview Message'), function() {
                frappe.call({
                    method: 'tap_buddy.api.campaign.preview_message',
                    args: {
                        template_name: frm.doc.template,
                        school_name: frm.doc.school_name
                    },
                    callback: function(r) {
                        if (r.message) {
                            frappe.msgprint({
                                title: __('Message Preview'),
                                message: `<pre style="white-space: pre-wrap; font-family: sans-serif;">${r.message}</pre>`
                            });
                        }
                    }
                });
            });
        }
    },
    template: function(frm) {
        if (frm.doc.template) {
            frappe.db.get_doc(
                "WhatsApp Template",
                frm.doc.template
            ).then((doc) => {
                const template = doc.message || doc.message_body || "";
                const cleaned = clean_message(template);
                const current = (frm.doc.message_template || "").trim();
                const previous_template = (frm.doc.__last_template_message || "").trim();

                if (!current || current === previous_template) {
                    frm.set_value("message_template", cleaned);
                } else {
                    frappe.msgprint({
                        title: __("Template Changed"),
                        message: __("Message Template was customized, so it was not overwritten."),
                        indicator: "orange"
                    });
                }

                frm.doc.__last_template_message = cleaned;
            });
        }
    }
});


function clean_message(html) {

    if (!html) return "";

    // Preserve line breaks before removing HTML
    html = html
        .replace(/<br\s*\/?>/gi, "\n")
        .replace(/<\/p>/gi, "\n\n")
        .replace(/<\/div>/gi, "\n");

    const div = document.createElement("div");
    div.innerHTML = html;

    return (div.textContent || "")
        .replace(/\n{3,}/g, "\n\n")
        .replace(/[ \t]+\n/g, "\n")
        .trim();
}

