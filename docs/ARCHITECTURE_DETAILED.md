# TAP Bench — Detailed Architecture & Code Map

**Purpose**: Provide an LLM- and engineer-friendly, detailed architecture document that explains components, data flows, module indexes, key functions/classes, DocType schemas, environment/config, run and test recipes, and reproducible traces for TAP Buddy + Frappe in this workspace.

**Location**: `docs/ARCHITECTURE_DETAILED.md`

--------------------------------------------------------------------------------
## 1. Executive Summary
--------------------------------------------------------------------------------
- The workspace contains a Frappe bench with two primary applications under `apps/`:
  - `apps/frappe` — The core Frappe framework.
  - `apps/tap_buddy` — TAP Buddy (Event-Driven WhatsApp Automation Platform).
- The system connects an external LMS (`lms.evalix.xyz`) to Glific (WhatsApp API).
- **Integration Model**: Bi-directional.
  - **LMS Sync**: Pulls master data (Students, Schools, Batches) from LMS APIs.
  - **Glific Sync**: Pushes HSM templates and WhatsApp messages to Glific APIs.
- **Dispatch Model**: Queue-first with Circuit Breakers. Campaigns are submitted, recipients are built and enqueued, background workers dispatch messages via Glific REST API, and webhooks update delivery statuses asynchronously.

--------------------------------------------------------------------------------
## 2. Components & Responsibilities
--------------------------------------------------------------------------------
- **Frappe Framework (`apps/frappe`)**: HTTP server, routing, background scheduler, DocType metadata, ORM, RBAC, and auto-generated REST APIs.
- **TAP Buddy (`apps/tap_buddy`)**: Domain logic for campaigns, recipients, Glific integration, HSM template lifecycle, LMS data mapping, scheduler jobs, and Cypress E2E UI testing.
- **Redis**: Job queue for `frappe.enqueue`, RQ workers, and **Circuit Breaker** state management (`tap_buddy:cb:glific`).
- **PostgreSQL**: Persistent storage for DocType records (including LMS mirrored records).
- **Glific API**: External WhatsApp provider (REST and GraphQL). Used to send messages, register templates (`createSessionTemplate`), and receive webhooks.
- **LMS API**: External system providing Student, School, and Batch data (`https://lms.evalix.xyz/api/resource/`).
- **Cypress**: End-to-end UI test runner located at `apps/tap_buddy/tests/ui/`.

--------------------------------------------------------------------------------
## 3. Per-Module Index & API Surface
--------------------------------------------------------------------------------
### Background Jobs & Utilities
- `tap_buddy/tasks/scheduler.py`
  - Defines cron and hourly background jobs (e.g., `process_pending_lms_events`, `sync_lms_students`, `retry_failed_messages`).
- `tap_buddy/services/redis_utils.py`
  - Rate limiting, distributed locks, and **Circuit Breaker** implementation (`check_circuit_breaker`, `record_api_failure`).

### External Sync Services (LMS & Glific)
- `tap_buddy/services/lms_student_sync.py` — Pulls Students from LMS, maps to Schools. Includes `@frappe.whitelist` API `sync_student(lms_id)`.
- `tap_buddy/services/lms_school_sync.py` — Pulls Schools from LMS. Includes `@frappe.whitelist` API `sync_school(lms_id)`.
- `tap_buddy/services/lms_batch_sync.py` — Pulls Batches from LMS. Includes `@frappe.whitelist` API `sync_batch(lms_id)`.
- `tap_buddy/services/webhook_processor.py` — Contains robust background processing logic for incoming webhook payloads to prevent timeouts.
- `tap_buddy/services/glific_client.py` — Core wrapper handling Auth, GraphQL/REST, Token Refresh logic, and Circuit Breaker integration.
- `tap_buddy/services/glific_template_service.py` — Whitelisted APIs to push HSM templates to Glific (`create_and_push_template`) and send test messages (`send_test_message`).

### API Endpoints (Webhook Receivers)
- `tap_buddy/api/webhook.py` — `@frappe.whitelist(allow_guest=True)` handler for Glific webhooks.
- `tap_buddy/api/lms_webhook.py` — `@frappe.whitelist(allow_guest=True)` handler for LMS webhooks.
- `tap_buddy/api/metrics.py` — `@frappe.whitelist` for extracting campaign metrics.
- `tap_buddy/api/replay.py` — Handlers for replaying failed webhooks (`replay_webhook`, `replay_all_failed_webhooks`).

### Cypress Tests
- `apps/tap_buddy/tests/ui/hsm_template_e2e_spec.js` — 6-step E2E Cypress test creating a template, pushing to Glific, and verifying real WhatsApp message delivery.

--------------------------------------------------------------------------------
## 4. DocType Schemas (Key Entities)
--------------------------------------------------------------------------------
**1. WhatsApp Template** (`whatsapp_template.json`)
- Tracks the physical message structure and its lifecycle on Glific.
- Fields: `template_name`, `message`, `glific_shortcode`, `language`, `category`, `glific_template_id`, `glific_db_id`, `glific_push_status` (PENDING/APPROVED), `glific_push_response`, `detected_params`.

**2. LMS Student** (`lms_student.json`)
- Fields: `lms_id`, `student_name`, `phone`, `glific_id`, `school` (Link), `lms_school_id`, `grade`, `section`, `gender`, `lms_status`, `last_synced_at`.

**3. LMS Batch** (`lms_batch.json`)
- Fields: `lms_id`, `batch_name`, `title`, `program_type`, `school` (Link), `is_active`, `current_week`, `total_weeks`, `start_date`, `end_date`, `last_synced_at`.

**4. TAP Campaign** (`tap_campaign.json`)
- Fields: `campaign_name`, `school_name` (Link to School), `template` (Link to WhatsApp Template), `message_template`, `status` (Draft, Queued, Processing, Sent, Failed, etc.), `targeting_type`.

**5. LMS Reminder Log** (`lms_reminder_log.json`)
- Tracks event-driven automations.
- Fields: `student_id`, `phone`, `reminder_type`, `dedup_key`, `status`, `glific_message_id`, `sent_at`, `context_json`, `error`.

**6. Campaign Recipient** (`campaign_recipient.json`)
- Represents a single physical message delivery attempt to an individual.
- Fields: `name`, `campaign`, `school`, `status` (Pending, Queued, Processing, Sent, Delivered, Read, Failed), `scheduled_time`, `sent_time`.

--------------------------------------------------------------------------------
## 5. Configuration Manifest
--------------------------------------------------------------------------------
Important settings defined in the **TAP Buddy Settings** single DocType:
- `glific_url` — Base API URL (e.g., `https://api.tap.glific.com/api/v1`).
- `glific_token`, `glific_access_token`, `glific_refresh_token` — Auth lifecycle tokens. (Glific token expiry can cause 401 errors, requiring manual refresh in UI).
- `glific_phone_number` — Sender phone number used for testing.
- LMS Settings: `lms_base_url`, `lms_api_key`, `webhook_secret`.

--------------------------------------------------------------------------------
## 6. Reproducible Traces
--------------------------------------------------------------------------------
### Trace A: HSM Template Creation
1. User creates `WhatsApp Template` in the UI.
2. The UI calls `glific_template_service.create_and_push_template()`.
3. The service builds a GraphQL payload for `createSessionTemplate` using `GlificClient`.
4. Glific responds with an `id` and `status` (Pending).
5. Frappe updates the template record with `glific_db_id` and `glific_push_status`.

### Trace B: Campaign Dispatch
1. UI submits `TAP Campaign` referencing a template.
2. `tap_campaign.py` `on_submit` hook enqueues a dispatch job.
3. The background worker uses `redis_utils.check_circuit_breaker("glific")` before making calls to prevent compounding errors.
4. Worker calls Glific API per recipient. Any exception triggers `record_api_failure()` (5 errors trip the breaker).
5. Glific webhooks later asynchronously update delivery statuses via `tap_buddy.api.webhook.handle`.

--------------------------------------------------------------------------------
## 7. Run & Test Recipes
--------------------------------------------------------------------------------
**Local Development Start:**
```bash
source env/bin/activate
bench start
```

**Run End-to-End HSM Integration Flow via Cypress:**
```bash
export NVM_DIR="$HOME/.nvm" && . "$NVM_DIR/nvm.sh" && nvm use 18
cd apps/tap_buddy
npx cypress run --spec "tap_buddy/tests/ui/hsm_template_e2e_spec.js" --config baseUrl=http://tapbuddy.local:8000
```

**Troubleshooting Guide:**
- **Glific Auth Errors (401 Not Authenticated):** Tokens expire frequently. Re-authenticate in `TAP Buddy Settings` by obtaining a fresh JWT from the Glific dashboard.
- **Circuit Breaker Open:** If the Glific API fails repeatedly (or you triggered bad data), the circuit breaker will block all outgoing requests. Clear the Redis key manually to recover:
  ```bash
  redis-cli -p 13000 DEL tap_buddy:cb:glific
  ```
- **Sync Issues:** You can manually trigger a full LMS sync using background workers by calling `tap_buddy.tasks.scheduler.sync_lms_students()`.

--------------------------------------------------------------------------------
Generated: 2026-05-29 — update as code changes.
