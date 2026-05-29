// ***********************************************
// Custom Cypress Commands for TAP Buddy
// ***********************************************

const HOST = { Host: "tapbuddy.local:8000" };

Cypress.Commands.add("frappeLogin", (username = "Administrator", password = Cypress.env("adminPassword") || "admin@123") => {
  cy.session("admin-session", () => {
    cy.request({
      method: "POST",
      url: "/api/method/login",
      headers: { ...HOST, "Content-Type": "application/json" },
      body: { usr: username, pwd: password },
    }).then((r) => {
      expect(r.status).to.eq(200);
      cy.log("✅ Logged in as " + username);
    });
  });
});

Cypress.Commands.add("frappeApi", (method, url, body = null) => {
  const opts = {
    method,
    url,
    headers: { ...HOST, "Content-Type": "application/json", "X-Frappe-CSRF-Token": "fetch" },
    failOnStatusCode: false,
  };
  if (body) opts.body = body;
  return cy.request(opts);
});

Cypress.Commands.add("frappeCreateDoc", (doctype, doc) => {
  return cy.frappeApi("POST", `/api/resource/${encodeURIComponent(doctype)}`, doc);
});

Cypress.Commands.add("frappeGetList", (doctype, filters, fields, limit=5) => {
  return cy.frappeApi(
    "GET",
    `/api/resource/${encodeURIComponent(doctype)}?` +
      `filters=${encodeURIComponent(JSON.stringify(filters))}&` +
      `fields=${encodeURIComponent(JSON.stringify(fields))}&limit=${limit}`
  );
});

Cypress.Commands.add("frappeCallMethod", (method, args = {}) => {
  return cy.frappeApi("POST", `/api/method/${method}`, args);
});

Cypress.Commands.add("frappeDeleteDoc", (doctype, name) => {
  return cy.frappeApi("DELETE", `/api/resource/${encodeURIComponent(doctype)}/${encodeURIComponent(name)}`);
});
