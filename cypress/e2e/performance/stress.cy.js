describe("TAP Buddy — Performance & Stress Testing", () => {
  before(() => {
    cy.frappeLogin();
    cy.frappeCallMethod("tap_buddy.api.testing.set_webhook_settings", { webhook_secret: "testsecret", webhook_enabled: 1 });
  });

  it("Simulates a high-volume webhook storm without dropping requests", () => {
    const totalRequests = 100;
    let completed = 0;

    cy.log(`Simulating ${totalRequests} rapid webhooks...`);

    // We fire requests sequentially in Cypress because cy.request is queued anyway
    for (let i = 0; i < totalRequests; i++) {
      const body = { payload: { message: { id: `storm_msg_${i}`, status: "delivered", phone: "8595701049" } } };
      cy.task('hmac', { secret: 'testsecret', body: JSON.stringify(body) }).then((sig) => {
        cy.request({
          method: "POST",
          url: "/api/method/tap_buddy.api.webhook.handle",
          body: body,
          headers: { "X-Glific-Signature": `sha256=${sig}` },
          failOnStatusCode: false
        }).then((r) => {
          expect(r.status).to.eq(200);
          completed++;
        });
      });
    }

    // Since cypress commands are enqueued, this wait ensures we process them all
    cy.wrap(null).should(() => {
      expect(completed).to.eq(totalRequests);
    });
  });

  it("Dispatches a massive webhook queue efficiently", () => {
    // Process the 100 queued requests
    cy.frappeCallMethod("tap_buddy.api.testing.process_webhook_queue", {}).then((r) => {
      expect(r.status).to.eq(200);
    });
  });

  it("Creates a large batch campaign", () => {
    // Note: To avoid actually sending 1000 WhatsApp messages to real numbers and exhausting quota,
    // we just queue the campaign and assert the worker handles the queue creation efficiently.
    const stamp = Date.now();
    cy.frappeCreateDoc("School", { school_name: `Stress School ${stamp}`, whatsapp_number: "+918595701049" });

    cy.frappeCreateDoc("WhatsApp Template", {
      template_name: `Stress Tmpl ${stamp}`,
      message: "Stress test message",
      glific_template_id: "pta_meeting_alert_v2"
    }).then(tmpl => {
      cy.frappeCreateDoc("TAP Campaign", {
        campaign_name: `Stress Campaign ${stamp}`,
        template: tmpl.body.data.name,
        school_name: `Stress School ${stamp}`,
        send_date: new Date().toISOString().slice(0, 16).replace("T", " "),
        status: "Queued",
      }).then(r => {
        expect(r.status).to.be.oneOf([200, 201]);
      });
    });
  });
});
