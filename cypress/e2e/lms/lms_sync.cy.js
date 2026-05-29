describe("TAP Buddy — LMS Sync Flows", () => {
  before(() => {
    cy.frappeLogin();
  });

  it("Syncs schools", () => {
    cy.frappeCallMethod("tap_buddy.services.lms_school_sync.sync_school", { lms_id: "test_school_1" });
  });

  it("Syncs students", () => {
    cy.frappeCallMethod("tap_buddy.services.lms_student_sync.sync_student", { lms_id: "test_student_1" });
  });

  it("Handles missing LMS fields gracefully", () => {
    cy.frappeCreateDoc("School", { school_name: "Temp Missing Phone" });
  });
});
