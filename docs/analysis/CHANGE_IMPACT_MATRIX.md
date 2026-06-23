# TAP Buddy Change Impact Matrix

This matrix is designed to help AI agents and human engineers understand the **blast radius** of common architectural and feature changes within the TAP Buddy system. 

Before making any modifications, consult this guide to ensure all downstream dependencies are handled.

---

## Add New LMS Event
When the external LMS starts sending a new event type (e.g., `Course Completion` or `Parent Teacher Meeting`).

**Files & Components Affected:**
1. `services/lms_ingestion.py` (Update event ingestion switch).
2. `services/lms_mapper.py` (Map JSON fields to TAP Buddy DocTypes).
3. `services/lms_automation_engine.py` (Add rule triggers for this new event).
4. `DocType: LMS Event Mapping` (Add the new event slug to the Frappe UI options).
5. `DocType: LMS Trigger Log` (Ensure logs capture the new event type).

---

## Add New BigQuery Resource
When Glific flow builders need a new piece of context from the data warehouse (e.g., `teacher_context`).

**Files & Components Affected:**
1. `api/glific_bq_webhook.py` (Update the `ALLOWED_RESOURCES` whitelist dictionary).
2. `services/bigquery_executor.py` (No changes needed if strictly using TVFs).
3. **GCP BigQuery:** A new Table-Valued Function (TVF) matching the mapped name must be deployed to the `MEL_datasets` dataset.

---

## Add New Campaign Type
When a new mode of message delivery is required (e.g., `Interactive Buttons` or `Media Broadcast`).

**Files & Components Affected:**
1. `DocType: TAP Campaign` (Add new dropdown option in the Frappe UI).
2. `services/recipients.py` (Update validation logic if the campaign type requires different audience checks).
3. `tasks/scheduler.py` (Update `_dispatch_recipient()` switch block).
4. `services/glific_client.py` (Add new GraphQL/REST methods for the specific message type).

---

## Add New Webhook
When a new external system needs to push data to TAP Buddy.

**Files & Components Affected:**
1. `api/{new_system}_webhook.py` (Create the whitelisted endpoint handler).
2. `DocType: Webhook Event` (Ensure payload schema fits, or create a new logging DocType).
3. `tasks/scheduler.py` (If processing asynchronously, add a new background cron job or reuse `process_pending_webhook_events`).
4. `services/webhook_processor.py` (Add a new batch processor handler for the system).

---

## Add New Scheduler
When introducing a new periodic background job (e.g., `sync_lms_grades`).

**Files & Components Affected:**
1. `hooks.py` (Register the path in `scheduler_events` under `cron`, `hourly`, or `daily`).
2. `tasks/scheduler.py` (Implement the entry point function).
3. `services/{feature}_sync.py` (Implement the core business logic).
4. **Operations:** `bench restart` must be run on the VM to reload the cron table into Supervisor.

---

## Add New DocType
When creating a new database table/entity.

**Files & Components Affected:**
1. **Frappe Desk UI:** The DocType must be created via the Frappe UI (`/app/doctype`) to generate the JSON schema.
2. `tap_buddy/tap_buddy/doctype/{doctype_name}/` (Generated directory containing Python controller and JS client scripts).
3. `hooks.py` (Only if the DocType requires special permission overrides or dashboard integrations).
4. **Git Tracking:** You must commit the generated `.json` and `.py` files.

---

## Modify LMS Schema
When the external LMS changes their JSON response format (e.g., renaming `studentId` to `id`).

**Files & Components Affected:**
1. `services/lms_mapper.py` (Update dictionary lookups).
2. `services/lms_client.py` (Update any pagination or nested response parsing).
3. `tests/test_lms_ingestion.py` (Update mock JSON payloads).

---

## Modify Glific Flow Sync
When Glific updates their GraphQL API schema for fetching Flows.

**Files & Components Affected:**
1. `services/glific_client.py` (Update the raw GraphQL query strings).
2. `services/flow_sync.py` (Update parsing logic for the paginated response).
3. `DocType: Glific Flow` (If new fields are synced, add them to the Frappe schema).


## WhatsApp Group vs Glific Collection

**Architectural Distinction:**
1. **WhatsApp Group (`glific_group_id`)**: The native ID of a WhatsApp Group inside Glific. This ID is used strictly for **Standard Group Messaging** (`sendGroupMessage`).
2. **Contact Collection (`glific_collection_id`)**: A Glific feature that groups contacts together. When starting a **Group Flow** (`startGroupFlow`), the Glific API strictly requires the ID of the **Contact Collection** representing the group, *not* the WhatsApp Group ID.

**Mapping Workflow:**
- `WhatsApp Group` records sync down the `glific_group_id`.
- `group_collection_sync.py` creates a `WhatsApp Group Collection Mapping` that links the `WhatsApp Group` to its corresponding `WhatsApp Group Collection`.
- When `_dispatch_flow_campaign` runs, it dynamically resolves the `glific_collection_id` via the `WhatsApp Group Collection Mapping`. If a mapping is missing or broken, the dispatch fails safely.
