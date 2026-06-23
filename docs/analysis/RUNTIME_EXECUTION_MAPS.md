# TAP Buddy Runtime Execution Maps

This document provides exact code execution paths across all major operational pipelines. Use this when debugging or assessing the impact of a code modification.

---

## 1. LMS Student Sync
* **Trigger:** Hourly Cron
* **Entry Point:** `hooks.py`
* **Function:** `tap_buddy.tasks.scheduler.sync_lms_students()`
* **Service:** `tap_buddy.services.lms_student_sync.sync_all_students()`
* **Client Call:** `tap_buddy.services.lms_client.get_students()` (Paginates LMS API)
* **Mapper:** `tap_buddy.services.lms_mapper.map_student()`
* **Database:** `UPSERT INTO tabLMS Student` (via Frappe ORM)
* **Log:** `INSERT INTO tabSync Job`

## 2. LMS Batch Sync
* **Trigger:** Hourly Cron
* **Entry Point:** `hooks.py`
* **Function:** `tap_buddy.tasks.scheduler.sync_lms_batches()`
* **Service:** `tap_buddy.services.lms_batch_sync.sync_all_batches()`
* **Client Call:** `tap_buddy.services.lms_client.get_batches()`
* **Database:** `UPSERT INTO tabLMS Batch`

## 3. LMS School Sync
* **Trigger:** Hourly Cron
* **Entry Point:** `hooks.py`
* **Function:** `tap_buddy.tasks.scheduler.sync_lms_schools()`
* **Service:** `tap_buddy.services.lms_school_sync.sync_all_schools()`
* **Client Call:** `tap_buddy.services.lms_client.get_schools()`
* **Database:** `UPSERT INTO tabSchool`

## 4. LMS Assignment Polling
* **Trigger:** 30-Minute Cron
* **Entry Point:** `hooks.py`
* **Function:** `tap_buddy.tasks.scheduler.poll_lms_assignments()`
* **Service:** `tap_buddy.services.lms_assignment_polling.poll_assignment_events()`
* **Client Call:** `tap_buddy.services.lms_client.get_recent_assignments()`
* **Processor:** Identifies missing submissions.
* **Worker:** Enqueues `create_campaign_for_assignment()` in `default` queue.
* **Database:** `INSERT INTO tabTAP Campaign` (Auto-creates reminder campaign).

## 5. LMS Automation Engine
* **Trigger:** Webhook Callback (from LMS)
* **Entry Point:** `api/lms_webhook.py` -> `handle()`
* **Queue:** Fast-paths directly to `services.lms_pipeline.process_event()` or pushes to `default` queue depending on payload weight.
* **Service:** `tap_buddy.services.lms_automation_engine.evaluate_rules()`
* **Database:** Checks `LMS Event Mapping` rules. If matched, `INSERT INTO tabLMS Trigger Log`.

## 6. Campaign Scheduling
* **Trigger:** Frappe Desk UI / Automated creation.
* **Entry Point:** User clicks "Submit" on `TAP Campaign` document.
* **Database:** Status changes from `Draft` -> `Scheduled` / `Queued`.

## 7. Campaign Dispatch
* **Trigger:** Minutely Cron
* **Entry Point:** `hooks.py` -> `tasks.scheduler.trigger_scheduled_campaigns()`
* **Queue:** `frappe.enqueue(dispatch_campaign, queue="default")`
* **Worker:** Redis pulls job -> `tasks.scheduler.dispatch_campaign()`
* **Service:** `services.recipients.build_campaign_recipients()`
* **Database:** `db_utils.get_pending_recipients_for_update()` (Executes `SELECT FOR UPDATE SKIP LOCKED` on `tabCampaign Recipient`).
* **Rate Limiter:** `services.redis_utils.consume_token_bucket()`
* **API:** `services.glific_client.send_message_with_hsm_fallback()`
* **Database:** `INSERT INTO tabDispatch Attempt`, `UPDATE tabCampaign Recipient`.

## 8. Flow Sync
* **Trigger:** Daily Cron
* **Entry Point:** `hooks.py` -> `services.flow_sync.sync_glific_flows()`
* **API:** `services.glific_client.get_flows()` (GraphQL query)
* **Database:** `DELETE tabGlific Flow` -> `INSERT INTO tabGlific Flow`

## 9. Template Sync
* **Trigger:** Manual Button or Daily Cron
* **Service:** `services.glific_template_service.sync_templates()`
* **API:** `services.glific_client.get_templates()`
* **Database:** `UPSERT INTO tabWhatsApp Template`

## 10. Group Collection Sync
* **Trigger:** Daily Cron
* **Service:** `services.group_collection_sync.sync_collections_and_groups()`
* **API:** `services.glific_client.get_collections()`
* **Database:** `UPSERT INTO tabWhatsApp Group Collection`

## 11. Delivery Tracking
* **Trigger:** External Webhook from Glific (Message Read/Delivered)
* **Entry Point:** `api/webhook.py` -> `handle()`
* **Database:** `INSERT INTO tabWebhook Event`
* **Queue:** 5-Minute Cron -> `tasks.scheduler.process_pending_webhook_events()`
* **Service:** `services.webhook_processor.process_webhook_batches()`
* **Database:** `UPDATE tabCampaign Recipient`

## 12. Webhook Replay
* **Trigger:** Manual Button in Frappe Desk
* **Entry Point:** `api/replay.py` -> `replay_webhook()`
* **Service:** `services.replay.re_evaluate_webhook()`
* **Queue:** Pushes payload back into `process_webhook_batches()`.

## 13. BigQuery Webhook
* **Trigger:** External Webhook from Glific Chatbot node
* **Entry Point:** `api/glific_bq_webhook.py` -> `handle()`
* **Validation:** Checks `secret` against `frappe.get_single('TAP Buddy Settings')`.
* **Mapping:** Looks up `ALLOWED_RESOURCES` dictionary.
* **Service:** `services.bigquery_executor.execute_tvf()`
* **Database:** Reads `/home/gcp-data/secrets/bigquery-sa.json`. Initializes BQ client.
* **Query:** `SELECT * FROM get_student_context_v1(@phone)`
* **Response:** Strips Frappe wrapper (`frappe.response.update()`) -> HTTP 200 JSON.
