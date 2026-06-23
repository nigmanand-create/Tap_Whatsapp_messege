# TAP Buddy Scheduler Reference

This document maps every scheduled job configured in `tap_buddy/hooks.py`, including its execution interval, logical entry point, downstream service chain, and known failure modes.

---

## 1. Minutely Jobs (`*/1 * * * *`)

### Trigger Scheduled Campaigns
* **Cron Expression:** `*/1 * * * *`
* **Entry Point:** `tasks.scheduler.trigger_scheduled_campaigns`
* **Service Chain:** `trigger_scheduled_campaigns` -> Enqueues `dispatch_campaign`
* **Dependencies:** `TAP Buddy Settings` (dispatch_start_hour, dispatch_end_hour), `TAP Campaign` statuses.
* **Failure Modes:** Redis queue full, worker crashes.
* **Recovery Steps:** Ensure `default` worker is running. Check `Error Log` for enqueue failures.

---

## 2. Fast Polling Jobs (`*/5 * * * *`, `*/10 * * * *`)

### Process Pending Webhook Events
* **Cron Expression:** `*/5 * * * *`
* **Entry Point:** `tasks.scheduler.process_pending_webhook_events`
* **Service Chain:** `process_webhook_batches` -> Updates `Campaign Recipient` statuses based on Glific callbacks.
* **Dependencies:** `Webhook Event` DocType records created via `api/webhook.py`.
* **Failure Modes:** Glific sends malformed JSON, missing payload parameters.
* **Recovery Steps:** Jobs are idempotent. Run manually if queued webhook events pile up.

### Process Pending LMS Events
* **Cron Expression:** `*/10 * * * *`
* **Entry Point:** `tasks.scheduler.process_pending_lms_events`
* **Service Chain:** `lms_ingestion.py` -> `lms_automation_engine.py`
* **Dependencies:** LMS triggering events hitting the `/api/lms_webhook` endpoint.
* **Failure Modes:** LMS API changes schema, mapping engine fails.
* **Recovery Steps:** View `LMS Trigger Log` and inspect error traces.

---

## 3. Half-Hourly Jobs (`0,30 * * * *`)

### Retry Failed Messages
* **Cron Expression:** `0,30 * * * *`
* **Entry Point:** `tasks.scheduler.retry_failed_messages`
* **Service Chain:** `get_failed_recipients_for_update` -> `consume_token_bucket` -> `_dispatch_recipient`
* **Dependencies:** `TAP Campaign` retry limits, `Campaign Recipient` retry counts.
* **Failure Modes:** Target number is blocked/banned (Glific Terminal Error).
* **Recovery Steps:** Job automatically marks terminal failures to prevent infinite retries.

### Poll LMS Assignments
* **Cron Expression:** `0,30 * * * *`
* **Entry Point:** `tasks.scheduler.poll_lms_assignments`
* **Service Chain:** `lms_assignment_polling.poll_assignment_events`
* **Dependencies:** LMS Client API.
* **Failure Modes:** LMS API timeout.
* **Recovery Steps:** Transient failure, next 30-min window will pick up delta.

---

## 4. Hourly Jobs (`hourly`)

### Sweep Stale Campaigns
* **Cron Expression:** `hourly`
* **Entry Point:** `tasks.scheduler.sweep_stale_campaigns`
* **Service Chain:** Marks > 24hr stale campaigns as `Failed` if recipients are stuck.

### Sync Campaign Counts
* **Cron Expression:** `hourly`
* **Entry Point:** `tasks.scheduler.sync_campaign_counts`
* **Service Chain:** Aggregates SQL `COUNT()` on `Campaign Recipient` table.

### Process Glific Sync
* **Cron Expression:** `hourly`
* **Entry Point:** `tasks.scheduler.process_glific_sync`
* **Service Chain:** `glific_sync.sync_glific`
* **Dependencies:** Glific GraphQL API token.

### Sync LMS Schools / Batches / Students
* **Cron Expression:** `hourly`
* **Entry Points:** `sync_lms_schools`, `sync_lms_batches`, `sync_lms_students`
* **Service Chain:** `lms_school_sync.py`, `lms_batch_sync.py`, `lms_student_sync.py`
* **Dependencies:** LMS Client API, `LMS Integration Settings`.
* **Failure Modes:** LMS credentials rotated/expired.
* **Recovery Steps:** Update keys in Frappe Desk and restart scheduler.

### Scheduled Health Check
* **Cron Expression:** `hourly`
* **Entry Point:** `tap_buddy_settings.scheduled_health_check`

---

## 5. Daily Jobs (`daily`)

### Sync Collections and Groups
* **Cron Expression:** `daily`
* **Entry Point:** `services.group_collection_sync.sync_collections_and_groups`
* **Dependencies:** Glific API.

### Sync Glific Flows
* **Cron Expression:** `daily`
* **Entry Point:** `services.flow_sync.sync_glific_flows`
* **Service Chain:** Fetches paginated flows from Glific to populate `Glific Flow` table.
