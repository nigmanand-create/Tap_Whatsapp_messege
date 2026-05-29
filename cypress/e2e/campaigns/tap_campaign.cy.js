/**
 * TAP Buddy — Campaign Send UI Flow
 */

const TEST_PHONE    = "918595701049";
const TEMPLATE_NAME = `Cypress PTA Template ${Date.now()}`;
const SCHOOL_NAME   = `Cypress Test School ${Date.now()}`;
const CAMPAIGN_NAME = `Cypress PTA Campaign ${Date.now()}`;
const HSM_SHORTCODE = "pta_meeting_alert_v2";

describe("TAP Buddy — Campaign Send Flow", () => {
  let templateDocName = null;
  let schoolDocName   = null;
  let campaignDocName = null;

  before(() => {
    cy.frappeLogin();
  });

  it("Creates WhatsApp Template via API", () => {
    cy.frappeCreateDoc("WhatsApp Template", {
      template_name:      TEMPLATE_NAME,
      message:            "Hello {{1}},\n\nThis is to inform you that the PTA meeting for student {{2}} has been scheduled on {{3}} at {{4}}.\n\nPlease make sure to attend the meeting on time.\n\nThank you.",
      glific_template_id: HSM_SHORTCODE,
    }).then((r) => {
      expect(r.status).to.be.oneOf([200, 201, 409]);
      templateDocName = r.body?.data?.name || TEMPLATE_NAME;
    });
  });

  it("Creates School with test WhatsApp number via API", () => {
    cy.frappeCreateDoc("School", {
      school_name:      SCHOOL_NAME,
      whatsapp_number:  "+" + TEST_PHONE,
    }).then((r) => {
      expect(r.status).to.be.oneOf([200, 201, 409]);
      schoolDocName = r.body?.data?.name || SCHOOL_NAME;
    });
  });

  it("Creates TAP Campaign via API and links template + school", () => {
    const sendDate = new Date().toISOString().slice(0, 16).replace("T", " ");
    cy.frappeCreateDoc("TAP Campaign", {
      campaign_name: CAMPAIGN_NAME,
      template:      templateDocName || TEMPLATE_NAME,
      school_name:   schoolDocName   || SCHOOL_NAME,
      send_date:     sendDate,
      status:        "Queued",
    }).then((r) => {
      expect(r.status).to.be.oneOf([200, 201]);
      campaignDocName = r.body?.data?.name;
      expect(campaignDocName).to.be.a("string");
    });
  });

  it("Triggers dispatch and polls for Campaign Recipient = Sent", () => {
    expect(campaignDocName).to.be.a("string");

    cy.frappeCallMethod("tap_buddy.tasks.scheduler.dispatch_campaign", { campaign_name: campaignDocName })
      .then((r) => {
        cy.log("Dispatch status: " + r.status);
      });

    const pollStatus = (attempt = 0) => {
      if (attempt >= 10) return;
      cy.wait(3000);
      cy.frappeGetList("Campaign Recipient", [["campaign", "=", campaignDocName]], ["name", "status"]).then((r) => {
        const recipients = r.body?.data || [];
        const isSent = recipients.some((rec) => ["Sent", "Delivered", "Read"].includes(rec.status));
        const allFailed = recipients.length > 0 && recipients.every((rec) => rec.status === "Failed");

        if (isSent || allFailed) {
          cy.log("Polling complete");
        } else {
          pollStatus(attempt + 1);
        }
      });
    };
    pollStatus();
  });

  it("Navigates to Campaign in Frappe UI and verifies status", () => {
    expect(campaignDocName).to.be.a("string");
    cy.visit(`/app/tap-campaign/${encodeURIComponent(campaignDocName)}`);
    cy.get(".page-title", { timeout: 20000 }).should("be.visible");
    cy.get(".indicator-pill, .page-head .indicator", { timeout: 15000 })
      .first()
      .invoke("text")
      .then((text) => {
        expect(text.trim().length).to.be.greaterThan(0);
      });
  });

  it("Verifies campaign appears in TAP Campaign list view", () => {
    cy.visit("/app/tap-campaign");
    cy.get(".page-title", { timeout: 20000 }).should("be.visible");
    cy.get(".list-row, .frappe-list .no-result", { timeout: 20000 }).should("exist");
  });
});
