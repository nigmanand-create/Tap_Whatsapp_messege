describe("TAP Buddy — Assignment/Reminders Flow", () => {
  before(() => {
    cy.frappeLogin();
  });

  it("Runs the process_pending_lms_events scheduler job safely", () => {
    cy.frappeCallMethod("tap_buddy.tasks.scheduler.process_pending_lms_events", {});
  });

  it("Generates a reminder log uniquely", () => {
    const stamp = Date.now();
    cy.frappeCreateDoc("LMS Reminder Log", {
      student_id: `student_${stamp}`,
      phone: "+918595701049",
      reminder_type: "CUSTOM",
      dedup_key: `dedup_${stamp}`,
      status: "Sent"
    }).then(r => {
      expect(r.status).to.be.oneOf([200, 201]);
    });
  });
});
