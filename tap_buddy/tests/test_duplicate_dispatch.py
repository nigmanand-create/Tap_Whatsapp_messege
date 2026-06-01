import frappe
from frappe.utils.background_jobs import get_queue
from tap_buddy.tasks.scheduler import trigger_scheduled_campaigns

def test_campaign_dispatch_deduplication():
    """
    Test that triggering dispatch for the same campaign multiple times
    results in exactly one job in the queue, while different campaigns
    are queued independently.
    """
    # Clean up any existing jobs
    q = get_queue("default")
    q.empty()

    # Clean up DB
    frappe.db.sql("DELETE FROM `tabTAP Campaign` WHERE name IN ('TEST-CAMP-DEDUP-1', 'TEST-CAMP-DEDUP-2')")
    frappe.db.commit()

    if not frappe.db.exists("WhatsApp Template", "Test Template"):
        frappe.get_doc({
            "doctype": "WhatsApp Template",
            "name": "Test Template",
            "template_name": "Test Template",
            "message": "Hello"
        }).insert(ignore_permissions=True)
        frappe.db.commit()

    # Create two test campaigns via raw SQL to bypass full Document validation for queue testing
    frappe.db.sql("""
        INSERT INTO `tabTAP Campaign` (name, campaign_name, status, send_date, template)
        VALUES ('TEST-CAMP-DEDUP-1', 'TEST-CAMP-DEDUP-1', 'Queued', '2020-01-01 10:00:00', 'Test Template'),
               ('TEST-CAMP-DEDUP-2', 'TEST-CAMP-DEDUP-2', 'Queued', '2020-01-01 10:00:00', 'Test Template')
    """)
    frappe.db.commit()

    # Mock get_job to simulate job existence for deduplication
    original_get_job = frappe.utils.background_jobs.get_job
    original_enqueue_call = frappe.utils.background_jobs.get_queue("default").__class__.enqueue_call
    
    enqueue_calls = []
    
    class FakeJob:
        def __init__(self, job_id):
            self.id = job_id
        def get_status(self, refresh=False):
            from rq.job import JobStatus
            return JobStatus.QUEUED

    def mock_get_job(job_id):
        # job_id here might not have the site prefix, but enqueue_calls has it.
        for enqueued in enqueue_calls:
            if job_id in enqueued:
                return FakeJob(job_id)
        return None
        
    def mock_enqueue_call(self, *args, **kwargs):
        job_id = kwargs.get("job_id")
        enqueue_calls.append(job_id)
        return FakeJob(job_id)

    frappe.utils.background_jobs.get_job = mock_get_job
    frappe.utils.background_jobs.get_queue("default").__class__.enqueue_call = mock_enqueue_call

    try:
        # 1. Trigger Scheduled Campaigns (should enqueue both c1 and c2)
        trigger_scheduled_campaigns()
        frappe.db.commit() # Required because of enqueue_after_commit=True
        
        # Check queue length
        initial_length = len(enqueue_calls)
        
        # 2. Trigger AGAIN (Simulate duplicate cron run)
        trigger_scheduled_campaigns()
        frappe.db.commit()
        
        # Verify that both campaigns have EXACTLY 1 queued job each
        c1_jobs = [j for j in enqueue_calls if "dispatch_campaign_TEST-CAMP-DEDUP-1" in j]
        c2_jobs = [j for j in enqueue_calls if "dispatch_campaign_TEST-CAMP-DEDUP-2" in j]

        assert len(c1_jobs) == 1, f"Expected exactly 1 job for c1, found {len(c1_jobs)}"
        assert len(c2_jobs) == 1, f"Expected exactly 1 job for c2, found {len(c2_jobs)}"
    finally:
        frappe.utils.background_jobs.get_job = original_get_job
        frappe.utils.background_jobs.get_queue("default").__class__.enqueue_call = original_enqueue_call

    # Cleanup
    q.empty()
    frappe.db.sql("DELETE FROM `tabTAP Campaign` WHERE name IN ('TEST-CAMP-DEDUP-1', 'TEST-CAMP-DEDUP-2')")
    frappe.db.commit()
