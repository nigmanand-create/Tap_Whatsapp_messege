frappe.listview_settings['LMS Student'] = {
	onload: function(listview) {
		// Set default page length to 50 to prevent massive rendering payloads
		listview.page_length = 50;
	}
};
