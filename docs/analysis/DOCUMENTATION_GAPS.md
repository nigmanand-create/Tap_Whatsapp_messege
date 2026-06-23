# TAP Buddy Documentation Gaps & Coverage Audit

## Phase 1: Documentation Coverage Report

| Component | File | Status | Missing Information |
| --------- | ---- | ------ | ------------------- |
| **API** | `api/bigquery.py` | Undocumented | Endpoint definitions, BQ schema syncing APIs. |
| **API** | `api/campaign.py` | Undocumented | Campaign triggering logic, endpoint inputs/outputs. |
| **API** | `api/glific_bq_webhook.py` | Fully Documented | None. (Covered in Webhook Guide) |
| **API** | `api/lms_webhook.py` | Undocumented | Webhook payload structure, HMAC validation rules. |
| **API** | `api/metrics.py` | Undocumented | Promethues/Metrics export schemas. |
| **API** | `api/replay.py` | Undocumented | Replay ID requirements, idempotent handling. |
| **API** | `api/testing.py` | Undocumented | Test fixtures and debug routes. |
| **API** | `api/webhook.py` | Undocumented | Glific status callbacks, delivery tracking format. |
| **API** | `api/whatsapp_browser.py` | Undocumented | Web WhatsApp scraping/browser interface specifics. |
| **Service** | `services/bigquery_executor.py` | Partially Documented| Fallback credential logic, specific JSON parsing errors. |
| **Service** | `services/db_utils.py` | Undocumented | Postgres locking strategies (`FOR UPDATE SKIP LOCKED`). |
| **Service** | `services/flow_sync.py` | Partially Documented| GraphQL pagination logic for Flows. |
| **Service** | `services/glific_client.py` | Partially Documented| Rate limit backing off, HTTP timeout handling. |
| **Service** | `services/glific_sync.py` | Undocumented | Glific bidirectional syncing logic. |
| **Service** | `services/glific_template_service.py`| Undocumented | HSM template syncing, variable parsing logic. |
| **Service** | `services/group_collection_sync.py` | Undocumented | WhatsApp Group sync and collection mapping. |
| **Service** | `services/lms_assignment_polling.py`| Undocumented | Assignment polling frequency, delta updates. |
| **Service** | `services/lms_automation_engine.py` | Undocumented | Rules engine parsing, dynamic campaign creation. |
| **Service** | `services/lms_batch_sync.py` | Undocumented | Batch student groupings, API pagination. |
| **Service** | `services/lms_client.py` | Undocumented | LMS authentication headers, endpoints used. |
| **Service** | `services/lms_ingestion.py` | Undocumented | LMS event ingestion pipeline and deduplication. |
| **Service** | `services/lms_mapper.py` | Undocumented | Translation from LMS JSON to Frappe DocTypes. |
| **Service** | `services/lms_pipeline.py` | Undocumented | Master orchestration pipeline for LMS events. |
| **Service** | `services/lms_school_sync.py` | Undocumented | School metadata syncing and linking. |
| **Service** | `services/lms_student_sync.py` | Undocumented | Student record upsert logic, unique ID constraints. |
| **Service** | `services/recipients.py` | Undocumented | SQL queries for Campaign Audience resolution. |
| **Service** | `services/redis_utils.py` | Undocumented | Token bucket rate limiting implementation. |
| **Service** | `services/replay.py` | Undocumented | Core replay mechanisms for failed webhooks. |
| **Service** | `services/template_renderer.py` | Undocumented | Jinja/HSM template rendering logic for WhatsApp. |
| **Service** | `services/webhook_processor.py` | Undocumented | Async processor for webhook batches. |
| **DocType** | `TAP Buddy Settings` | Partially Documented| Missing dispatch window variables. |
| **DocType** | `TAP BigQuery Settings` | Partially Documented| Misses edge cases on JSON vs Path fields. |
| **DocType** | `TAP Campaign` | Partially Documented| Missing variables for HSM templates. |
| **DocType** | `Campaign Recipient` | Partially Documented| Status transition states missing. |
| **DocType** | `20+ LMS DocTypes` | Undocumented | (e.g. `lms_student`, `school_group`, etc.) missing entirely. |
| **Scheduler**| `hooks.py` (14 Crons) | Undocumented | Hourly, minutely, daily jobs missing from docs. |
| **Integrations**| `LMS` | Undocumented | Full LMS API contract missing. |
| **Integrations**| `Glific` | Partially Documented| GraphQL vs REST differences missing. |

---

## Phase 2: Coverage Metrics

* **APIs:** 11% (1/9)
* **Services:** 9% (2/21)
* **DocTypes:** 16% (4/24)
* **Schedulers:** 0% (0/14)
* **Integrations:** 50% (BigQuery & Webhooks, but missing LMS entirely)

**Overall Documentation Completeness Score:** 15/100

---

## Phase 3: Runtime Execution Maps

### LMS Student Sync
```text
hooks.py -> hourly cron
→ tap_buddy.tasks.scheduler.sync_lms_students()
→ tap_buddy.services.lms_student_sync.sync_all_students()
→ tap_buddy.services.lms_client.py (Fetch Students API)
→ tap_buddy.services.lms_mapper.py (Map to DB)
→ Database (INSERT INTO `tabLMS Student`)
```

### Campaign Execution (Dispatch)
```text
hooks.py -> minute cron
→ tap_buddy.tasks.scheduler.trigger_scheduled_campaigns()
→ frappe.enqueue("tap_buddy.tasks.scheduler.dispatch_campaign", queue="default")
→ redis_queue (default)
→ Background Worker
→ tap_buddy.tasks.scheduler.dispatch_campaign()
→ tap_buddy.services.recipients.build_campaign_recipients()
→ tap_buddy.services.db_utils.get_pending_recipients_for_update() (Locks DB)
→ tap_buddy.services.redis_utils.consume_token_bucket() (Rate Limit)
→ tap_buddy.services.glific_client.send_message_with_hsm_fallback()
```

### Delivery Tracking (Glific -> TAP Buddy)
```text
Glific Webhook
→ HTTP POST
→ tap_buddy.api.webhook.handle()
→ Database (INSERT `Webhook Event`)
→ tap_buddy.tasks.scheduler.process_pending_webhook_events() (5 min cron)
→ tap_buddy.services.webhook_processor.process_webhook_batches()
→ Database (UPDATE `Campaign Recipient` status='Delivered')
```

---

## Phase 4: Configuration Dependency Graph

### TAP Buddy Settings
* `webhook_secret` (Required): Used by `api/glific_bq_webhook.py`. Failure = 401 Unauthorized.
* `dispatch_start_hour` / `dispatch_end_hour` (Optional): Used by `tasks/scheduler.py`. Failure = Dispatch suspended outside windows.
* `rate_limit` / `batch_size` (Required): Used by `tasks/scheduler.py` & `redis_utils.py`. Failure = OOM or Glific 429 bans.

### TAP BigQuery Settings
* `enabled` (Required): Used by `bigquery_executor.py`. Failure = BigQuery webhook disabled.
* `project_id` / `dataset_id` (Required): Used by `bigquery_executor.py`. Failure = TVF query errors.
* `service_account_json` (Required): Used by `bigquery_executor.py`. Failure = GCP Auth errors.

### LMS Integration Settings
* `lms_base_url` / `api_key` (Required): Used by `lms_client.py`. Failure = LMS Syncs fail and log to `Sync Job`.

### Glific Sync Settings
* `glific_url` / `auth_token` / `phone_number` (Required): Used by `glific_client.py`. Failure = Unable to send messages or sync templates.

---

## Phase 6: AI Agent Readiness Assessment

**Can an AI safely modify the repository today?** -> **NO**

1. **Can I understand the purpose of the application?** PARTIAL. BigQuery/Glific is clear, but LMS Pipeline is obscured.
2. **Can I understand the architecture?** NO. Queuing models (`FOR UPDATE SKIP LOCKED`) and rate limiters (`redis token bucket`) are completely hidden. AI might introduce race conditions.
3. **Can I understand every integration?** NO. LMS APIs and Group Collections are undocumented.
4. **Can I deploy the application?** PARTIAL. Frappe concepts are present, but LMS Webhook configurations aren't.
5. **Can I debug production failures?** NO. Replay mechanisms (`api/replay.py`) and Webhook Event batch processors aren't mapped.
6. **Can I safely modify code?** NO. High risk of modifying `tasks/scheduler.py` and bypassing rate limit token buckets, causing Glific bans.
7. **Can I identify dangerous files?** NO. `services/db_utils.py` contains raw locking SQL. An AI might rewrite this inefficiently.

**Documentation Needed:** An explicit AI Orientation Guide detailing the `FOR UPDATE SKIP LOCKED` requirement, Frappe enqueue mechanics, Rate Limit Bucket handling, and the complete LMS event ingestion pipeline.
