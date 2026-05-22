context("TAP Buddy", () => {
	before(() => {
		cy.login("Administrator", Cypress.env("adminPassword") || "root");
		cy.visit("/desk");
	});

	it("creates campaign and auto-fills message template", () => {
		cy.set_value("TAP Buddy Settings", "TAP Buddy Settings", {
			sync_mode_fallback: 1,
			glific_url: "https://api.glific.test/v1",
			glific_token: "test-token",
			batch_size: 5,
			rate_limit: 5,
			retry_count: 1,
			dispatch_start_hour: "00:00:00",
			dispatch_end_hour: "23:59:59",
		});

		const stamp = Date.now();
		const schoolName = `Auto School ${stamp}`;
		const templateName = `Auto Template ${stamp}`;
		const campaignName = `Auto Campaign ${stamp}`;

		cy.insert_doc(
			"School",
			{
				school_name: schoolName,
				principal_name: "Auto Principal",
				whatsapp_number: "+919999999999",
				state: "Auto State",
				district: "Auto District",
				udise_code: `${stamp}`,
				block: "Auto Block",
			},
			true
		);

		cy.insert_doc(
			"WhatsApp Template",
			{
				template_name: templateName,
				message: "Hello {{ school_name }}\nLine 2",
			},
			true
		);

		cy.new_form("TAP Campaign");
		cy.fill_field("campaign_name", campaignName, "Data");
		cy.fill_field("school_name", schoolName, "Link");
		cy.fill_field("template", templateName, "Link");
		cy.fill_field("send_date", "2000-01-01 00:00:00", "Datetime");

		cy.get('[data-fieldname="message_template"] textarea')
			.should("be.visible")
			.and("contain.value", "Hello");

		cy.intercept("POST", "/api/method/frappe.desk.form.save.savedocs").as("save_call");
		cy.get(".primary-action").contains("Save").click({ force: true });
		cy.wait("@save_call");
		cy.click_doc_primary_button("Submit");
		cy.click_modal_primary_button("Yes");
		cy.get('[data-fieldname="status"] .control-value').should("contain", "Queued");

		cy.window().then((win) => {
			const name = win.cur_frm.doc.name;
			return cy.get_list("Campaign Recipient", ["name"], [["campaign", "=", name]]);
		}).then((res) => {
			expect(res.data.length).to.be.greaterThan(0);
		});
	});
});
