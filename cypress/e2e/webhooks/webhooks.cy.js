describe("TAP Buddy — Webhooks Flow", () => {
  before(() => {
    cy.frappeLogin();
    cy.frappeCallMethod("tap_buddy.api.testing.set_webhook_settings", { webhook_secret: "testsecret", webhook_enabled: 1 });
    cy.frappeCallMethod("tap_buddy.api.testing.set_lms_settings", { webhook_secret: "testsecret", enabled: 1 });
  });

  it("Accepts glific webhooks gracefully via the unauthenticated API endpoint", () => {
    const body = { payload: { message: { id: `glific_msg_${Date.now()}`, status: "delivered", phone: "8595701049" } } };
    cy.task('hmac', { secret: 'testsecret', body: JSON.stringify(body) }).then((sig) => {
      cy.request({
        method: "POST",
        url: "/api/method/tap_buddy.api.webhook.handle",
        body: body,
        headers: { "X-Glific-Signature": `sha256=${sig}` },
        failOnStatusCode: false
      }).then((r) => {
        expect(r.status).to.eq(200);
      });
    });
  });

  it("Accepts LMS webhooks gracefully", () => {
    const body = { event_type: "assignment.due", student_id: "student_abc", due_date: "2026-05-28" };
    cy.task('hmac', { secret: 'testsecret', body: JSON.stringify(body) }).then((sig) => {
      cy.request({
        method: "POST",
        url: "/api/method/tap_buddy.api.lms_webhook.handle",
        body: body,
        headers: { "X-LMS-Signature": `sha256=${sig}` },
        failOnStatusCode: false
      }).then((r) => {
        expect(r.status).to.eq(200);
      });
    });
  });

  it("Triggers the internal webhook processor job to empty the redis queue", () => {
    cy.frappeCallMethod("tap_buddy.api.testing.process_webhook_queue", {});
  });
});
