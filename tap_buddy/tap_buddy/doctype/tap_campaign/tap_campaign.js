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
        
        frm.set_query("target_collection", function() {
            return {
                query: "tap_buddy.api.campaign.get_populated_collections"
            };
        });
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

                frm.set_value("message_template", cleaned);
                frm.doc.__last_template_message = cleaned;
                
                // Auto-populate Variable Mappings
                const matches = cleaned.match(/\{\{(\d+)\}\}/g);
                if (matches) {
                    let num_vars = 0;
                    matches.forEach(match => {
                        const num = parseInt(match.replace(/\D/g, ''));
                        if (num > num_vars) num_vars = num;
                    });
                    
                    frm.clear_table("variable_mappings");
                    for (let i = 1; i <= num_vars; i++) {
                        let row = frm.add_child("variable_mappings");
                        row.variable_number = i;
                        // Defaults for convenience
                        if (i === 1) {
                            row.mapping_type = "School Field";
                            row.field_name = "contact_name";
                        } else if (i === 2) {
                            row.mapping_type = "Student Field";
                            row.field_name = "child_name";
                        }
                    }
                    frm.refresh_field("variable_mappings");
                } else {
                    frm.clear_table("variable_mappings");
                    frm.refresh_field("variable_mappings");
                }
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

