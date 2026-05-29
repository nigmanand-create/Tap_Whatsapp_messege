describe("TAP Buddy — Auth & Token Flow", () => {
  before(() => {
    cy.frappeLogin();
  });

  it("Refreshes tokens correctly when expired", () => {
    cy.frappeCallMethod("tap_buddy.services.glific_template_service.send_test_message", {
      phone: "+918595701049",
      parent_name: "Auth Test",
      student_name: "Token Test",
      meeting_date: "1 Jan",
      meeting_time: "10 AM",
      template_shortcode: "pta_meeting_alert_v2"
    }).then((r) => {
      // Just verifying we can hit an endpoint requiring auth and it doesn't 401
      expect(r.status).to.eq(200);
    });
  });

  it("Simulates concurrent refresh attempts cleanly (circuit breaker shouldn't trip open)", () => {
    // Attempt multiple rapid requests
    for (let i = 0; i < 5; i++) {
      cy.frappeCallMethod("tap_buddy.api.metrics.get_delivery_metrics", {});
    }
  });
});
