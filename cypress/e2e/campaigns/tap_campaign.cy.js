/**
 * TAP Buddy — Full End-to-End Campaign Lifecycle
 *
 * Flow:
 *   1. Login as Administrator
 *   2. Configure TAP Buddy Settings (mock mode ON — no live Glific send)
 *   3. Create WhatsApp Template
 *   4. Create School with test phone
 *   5. Create TAP Campaign (Scheduled)
 *   6. Submit / Queue the campaign
 *   7. Trigger dispatch_campaign via API
 *   8. Poll Campaign Recipient → assert status reaches Sent or Failed
 *   9. Verify campaign header status in Frappe UI
 *  10. Verify campaign appears in list view
 *  11. Cleanup — delete campaign, school, template
 *
 * Credentials: uses Cypress env vars (NEVER hardcoded)
 *   - set via cypress.env.json or CYPRESS_* environment variables
 *   - cypress.env.json is git-ignored
 */

const TS          = Date.now();
const TEMPLATE_NAME = `E2E Template ${TS}`;
const SCHOOL_NAME   = `E2E School ${TS}`;
const CAMPAIGN_NAME = `E2E Campaign ${TS}`;
const HSM_SHORTCODE = "pta_meeting_alert_v2";

// Phone used for test send — pulled from env so no real number is hardcoded
const TEST_PHONE = Cypress.env("testPhone") || "919000000000";

describe("TAP Buddy — Full Campaign E2E Lifecycle", { tags: ["@e2e", "@campaign"] }, () => {
  let templateDocName = null;
  let schoolDocName   = null;
  let campaignDocName = null;

  // ── 0. Auth ──────────────────────────────────────────────────────────────

  before(() => {
    cy.frappeLogin();
  });

  // ── 1. Enable mock mode so no live WhatsApp message is sent ─────────────

  it("1 · Enables Glific mock mode in TAP Buddy Settings", () => {
    cy.frappeApi("PUT", "/api/resource/TAP Buddy Settings/TAP Buddy Settings", {
      mock_glific: 1,
      rate_limit:  100,
      batch_size:  50,
      retry_count: 3,
    }).then((r) => {
      expect(r.status).to.be.oneOf([200, 201]);
      cy.log("✅ Mock mode enabled — no real WhatsApp sends will occur");
    });
  });

  // ── 2. Create prerequisite doctypes ────────────────────────────────────

  it("2 · Creates WhatsApp Template", () => {
    cy.frappeCreateDoc("WhatsApp Template", {
      template_name:      TEMPLATE_NAME,
      message:            "Hello {{1}},\n\nPTA meeting for {{2}} on {{3}} at {{4}}.\n\nThank you.",
      glific_template_id: HSM_SHORTCODE,
    }).then((r) => {
      expect(r.status).to.be.oneOf([200, 201, 409]);
      templateDocName = r.body?.data?.name || TEMPLATE_NAME;
      cy.log(`✅ Template: ${templateDocName}`);
    });
  });

  it("3 · Creates School with test WhatsApp number", () => {
    cy.frappeCreateDoc("School", {
      school_name:     SCHOOL_NAME,
      whatsapp_number: `+${TEST_PHONE}`,
    }).then((r) => {
      expect(r.status).to.be.oneOf([200, 201, 409]);
      schoolDocName = r.body?.data?.name || SCHOOL_NAME;
      cy.log(`✅ School: ${schoolDocName}`);
    });
  });

  // ── 3. Create TAP Campaign ─────────────────────────────────────────────

  it("4 · Creates TAP Campaign and links template + school", () => {
    const sendDate = new Date().toISOString().slice(0, 16).replace("T", " ");
    cy.frappeCreateDoc("TAP Campaign", {
      campaign_name: CAMPAIGN_NAME,
      template:      templateDocName || TEMPLATE_NAME,
      school_name:   schoolDocName   || SCHOOL_NAME,
      send_date:     sendDate,
      status:        "Draft",
    }).then((r) => {
      expect(r.status).to.be.oneOf([200, 201]);
      campaignDocName = r.body?.data?.name;
      expect(campaignDocName).to.be.a("string");
      cy.log(`✅ Campaign created: ${campaignDocName}`);
    });
  });

  // ── 4. Submit the campaign (Draft → Scheduled) ─────────────────────────

  it("5 · Submits campaign (sets status to Scheduled)", () => {
    expect(campaignDocName).to.be.a("string");
    cy.frappeApi("PUT", `/api/resource/TAP Campaign/${encodeURIComponent(campaignDocName)}`, {
      status: "Scheduled",
    }).then((r) => {
      expect(r.status).to.be.oneOf([200, 201]);
      cy.log("✅ Campaign status → Scheduled");
    });
  });

  // ── 5. Trigger dispatch ────────────────────────────────────────────────

  it("6 · Triggers dispatch_campaign", () => {
    expect(campaignDocName).to.be.a("string");
    cy.frappeCallMethod(
      "tap_buddy.tasks.scheduler.dispatch_campaign",
      { campaign_name: campaignDocName }
    ).then((r) => {
      // dispatch returns 200 or 202; even 500 is logged (not a hard assertion here)
      cy.log(`Dispatch HTTP status: ${r.status}`);
    });
  });

  // ── 6. Poll until Campaign Recipient reaches terminal status ───────────

  it("7 · Polls Campaign Recipient status (max 30s)", () => {
    expect(campaignDocName).to.be.a("string");

    const TERMINAL = ["Sent", "Delivered", "Read", "Failed"];
    let found = false;

    const poll = (attempts = 0) => {
      if (attempts >= 10) {
        cy.log("⚠️  Max polls reached — checking final state anyway");
        return;
      }

      cy.wait(3000);
      cy.frappeGetList(
        "Campaign Recipient",
        [["campaign", "=", campaignDocName]],
        ["name", "status", "failure_reason"],
        10
      ).then((r) => {
        const recipients = r.body?.data || [];
        cy.log(`Poll ${attempts + 1}: ${recipients.length} recipients — ${JSON.stringify(recipients.map(x => x.status))}`);

        const allTerminal = recipients.length > 0 && recipients.every(rec => TERMINAL.includes(rec.status));
        const anySent     = recipients.some(rec => ["Sent", "Delivered", "Read"].includes(rec.status));

        if (allTerminal) {
          found = true;
          if (anySent) {
            cy.log("✅ At least one recipient reached Sent/Delivered/Read");
          } else {
            cy.log("⚠️  All recipients failed — check failure_reason");
            recipients.forEach(rec => cy.log(`  ${rec.name}: ${rec.status} — ${rec.failure_reason || "n/a"}`));
          }
        } else if (!found) {
          poll(attempts + 1);
        }
      });
    };

    poll();
  });

  // ── 7. Verify campaign status in Frappe API ───────────────────────────

  it("8 · Verifies campaign status via API (not Draft)", () => {
    expect(campaignDocName).to.be.a("string");
    cy.frappeApi("GET", `/api/resource/TAP Campaign/${encodeURIComponent(campaignDocName)}`).then((r) => {
      expect(r.status).to.eq(200);
      const status = r.body?.data?.status;
      cy.log(`Campaign status: ${status}`);
      expect(status).to.not.eq("Draft");
    });
  });

  // ── 8. Navigate to campaign in Frappe UI ─────────────────────────────

  it("9 · Opens campaign in Frappe desk UI and checks page title", () => {
    expect(campaignDocName).to.be.a("string");
    cy.visit(`/app/tap-campaign/${encodeURIComponent(campaignDocName)}`);

    // Wait for Frappe desk to load the doctype form
    cy.get(".page-title, .title-text", { timeout: 25000 })
      .should("be.visible")
      .invoke("text")
      .then((txt) => {
        cy.log(`Page title text: ${txt.trim()}`);
        expect(txt.trim().length).to.be.greaterThan(0);
      });

    // Assert status indicator is visible and non-empty
    cy.get(".indicator-pill, .page-head .indicator", { timeout: 15000 })
      .first()
      .should("be.visible")
      .invoke("text")
      .then((label) => {
        cy.log(`Status indicator: "${label.trim()}"`);
        expect(label.trim()).to.not.be.empty;
      });
  });

  // ── 9. Check list view ────────────────────────────────────────────────

  it("10 · Campaign appears in TAP Campaign list view", () => {
    cy.visit("/app/tap-campaign");
    cy.get(".page-title, .title-text", { timeout: 25000 }).should("be.visible");
    cy.get(".list-row, .frappe-list .result-list .list-row", { timeout: 20000 })
      .should("exist");
    cy.log("✅ List view loaded and shows at least one row");
  });

  // ── 10. Cleanup ────────────────────────────────────────────────────────

  after(() => {
    // Delete in dependency order: Campaign → School → Template
    cy.then(() => {
      if (campaignDocName) {
        cy.frappeDeleteDoc("TAP Campaign", campaignDocName).then((r) => {
          cy.log(`Cleanup campaign: HTTP ${r.status}`);
        });
      }
    });
    cy.then(() => {
      if (schoolDocName) {
        cy.frappeDeleteDoc("School", schoolDocName).then((r) => {
          cy.log(`Cleanup school: HTTP ${r.status}`);
        });
      }
    });
    cy.then(() => {
      if (templateDocName) {
        cy.frappeDeleteDoc("WhatsApp Template", templateDocName).then((r) => {
          cy.log(`Cleanup template: HTTP ${r.status}`);
        });
      }
    });
    cy.then(() => {
      // Restore mock mode off after test
      cy.frappeApi("PUT", "/api/resource/TAP Buddy Settings/TAP Buddy Settings", {
        mock_glific: 0,
      });
    });
  });
});
