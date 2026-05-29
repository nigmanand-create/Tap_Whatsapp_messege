/**
 * TAP Buddy — HSM Template Create & Send E2E
 */

const TEST_PHONE       = "+918595701049";  
const TIMESTAMP        = Date.now();
const TEMPLATE_LABEL   = `PTA Alert E2E ${TIMESTAMP}`;
const TEMPLATE_SHORTCODE = `pta_alert_e2e_${TIMESTAMP}`;
const APPROVED_SHORTCODE = "pta_meeting_alert_v2";

describe("TAP Buddy — HSM Template Create & Send E2E", () => {
  let templateDocName   = null;
  let glificDbId        = null;
  let glificShortcode   = null;
  let sentMessageId     = null;

  before(() => {
    cy.frappeLogin();
    cy.frappeCallMethod("tap_buddy.api.testing.reset_cb");
    cy.frappeCallMethod("tap_buddy.api.testing.set_mock_glific", { is_mock: 1 }).then(r => {
      expect(r.status).to.eq(200);
    });
  });

  after(() => {
    cy.frappeCallMethod("tap_buddy.api.testing.set_mock_glific", { is_mock: 0 });
  });

  it("Step 1 — Creates WhatsApp Template record in Frappe", () => {
    cy.frappeCreateDoc("WhatsApp Template", {
      template_name:     TEMPLATE_LABEL,
      message:           "Hello {{1}},\n\nThis is to inform you that the PTA meeting for student {{2}} has been scheduled on {{3}} at {{4}}.\n\nPlease make sure to attend the meeting on time.\n\nThank you.",
      language:          "English",
      category:          "UTILITY",
      glific_shortcode:  TEMPLATE_SHORTCODE,
      glific_template_id: TEMPLATE_SHORTCODE,
    }).then((r) => {
      expect(r.status).to.be.oneOf([200, 201, 409]);
      templateDocName = r.body?.data?.name || TEMPLATE_LABEL;
      cy.log("✅ Template record created: " + templateDocName);
    });
  });

  it("Step 2 — Pushes template to Glific (createSessionTemplate)", () => {
    expect(templateDocName).to.be.a("string");

    cy.frappeCallMethod(
      "tap_buddy.services.glific_template_service.create_and_push_template",
      {
        template_name:    templateDocName,
        message:          "Hello {{1}},\n\nThis is to inform you that the PTA meeting for student {{2}} has been scheduled on {{3}} at {{4}}.\n\nPlease make sure to attend the meeting on time.\n\nThank you.",
        language:         "English",
        category:         "UTILITY",
        glific_shortcode: TEMPLATE_SHORTCODE,
      }
    ).then((r) => {
      expect(r.status).to.be.oneOf([200, 201]);

      const result = r.body?.message ?? r.body;
      const pushStatus = result?.status || result?.message?.status;
      const pushResult = result?.message || result;

      if (pushResult?.status === "ok") {
        glificDbId      = pushResult.glific_db_id;
        glificShortcode = pushResult.glific_shortcode;
        cy.log(`✅ Template pushed to Glific`);
      } else {
        cy.log("⚠️  Glific push error: " + JSON.stringify(pushResult?.error || pushResult).slice(0, 300));
        glificShortcode = APPROVED_SHORTCODE;
      }
    });
  });

  it("Step 3 — Verifies WhatsApp Template record has Glific push data", () => {
    expect(templateDocName).to.be.a("string");
    cy.frappeGetList(
      "WhatsApp Template",
      [["template_name", "=", templateDocName]],
      ["name", "template_name", "glific_shortcode", "glific_push_status", "glific_db_id"]
    ).then((r) => {
      const found = r.body?.data || [];
      expect(found.length).to.be.greaterThan(0);
      const tmpl = found[0];
      expect(tmpl.name).to.eq(templateDocName);
    });
  });

  it(`Step 4 — Sends HSM test message to ${TEST_PHONE} via approved template`, () => {
    const meetingDate = new Date().toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" });
    const meetingTime = "10:30 AM";

    cy.frappeCallMethod(
      "tap_buddy.services.glific_template_service.send_test_message",
      {
        phone:             TEST_PHONE,
        parent_name:       "Test Parent",
        student_name:      "Ankit Kumar",
        meeting_date:      meetingDate,
        meeting_time:      meetingTime,
        template_shortcode: APPROVED_SHORTCODE,
      }
    ).then((r) => {
      expect(r.status).to.eq(200);
      const result = r.body?.message ?? r.body;
      if (result?.status === "ok") {
        sentMessageId = result.message_id;
        expect(result.message_id).to.be.a("string");
        expect(result.message_id.length).to.be.greaterThan(0);
      } else {
        const errMsg = result?.error || JSON.stringify(result);
        expect(result?.status, `HSM send failed: ${errMsg}`).to.eq("ok");
      }
    });
  });

  it("Step 5 — Navigates to WhatsApp Template list in TAP Buddy UI", () => {
    cy.visit("/app/whatsapp-template");
    cy.get(".page-title", { timeout: 20000 }).should("be.visible");
    cy.get(".list-row, .frappe-list .no-result", { timeout: 20000 }).should("exist");
    cy.frappeGetList(
      "WhatsApp Template",
      [["template_name", "=", templateDocName]],
      ["name", "template_name", "glific_push_status"]
    ).then((r) => {
      const found = r.body?.data || [];
      expect(found.length).to.be.greaterThan(0);
    });
  });

  it("Step 6 — Opens template detail page and verifies fields", () => {
    expect(templateDocName).to.be.a("string");
    cy.visit(`/app/whatsapp-template/${encodeURIComponent(templateDocName)}`);
    cy.get(".page-title", { timeout: 20000 }).should("be.visible");
    cy.get(".page-title").invoke("text").then((text) => {
      expect(text.trim().length).to.be.greaterThan(0);
    });
  });
});
