frappe.listview_settings['Glific Flow'] = {
    onload: function(listview) {
        listview.page.add_inner_button(__("Sync Flows from Glific"), function() {
            frappe.call({
                method: "tap_buddy.services.flow_sync.sync_glific_flows",
                freeze: true,
                freeze_message: __("Syncing active flows from Glific..."),
                callback: function(r) {
                    if(r.message) {
                        frappe.msgprint({
                            title: __('Success'),
                            indicator: 'green',
                            message: __('Successfully synced Glific Flows!')
                        });
                        listview.refresh();
                    } else {
                        frappe.msgprint({
                            title: __('Failed'),
                            indicator: 'red',
                            message: __('Failed to sync flows. Check Error Log for details.')
                        });
                    }
                }
            });
        });
    }
};
