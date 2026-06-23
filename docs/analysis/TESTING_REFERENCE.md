# TAP Buddy Testing Reference

This document maps all test files located in `tap_buddy/tests/`, providing guidance for modifying them and explaining which functionality they protect.

---

## 1. Unit Tests (Isolated Business Logic)

### `test_bigquery.py`
* **Purpose:** Validates BQ credential fallback logic (Filesystem vs DB) and JSON parsing.
* **Protected Functionality:** Webhook SQL execution via GCP.
* **Criticality:** HIGH. Do not modify without verifying against `/home/gcp-data/secrets/` path assumptions.
* **Retention:** Keep.

### `test_glific_bq_webhook.py`
* **Purpose:** Validates `api/glific_bq_webhook.py` HTTP routing, signature validation, and whitelist filtering.
* **Protected Functionality:** Glific Webhooks.
* **Criticality:** CRITICAL.
* **Safe Modification:** Ensure `frappe.flags.in_test` is maintained to prevent `frappe.response` mutations from breaking test runners.
* **Retention:** Keep.

### `test_redis_utils.py`
* **Purpose:** Validates the Token Bucket rate limiting algorithm.
* **Protected Functionality:** Campaign dispatch throttling.
* **Criticality:** HIGH. Prevents catastrophic Glific API bans (HTTP 429).
* **Retention:** Keep.

### `test_hsm_fallback.py`
* **Purpose:** Ensures parameters are mapped correctly into WhatsApp HSM templates.
* **Protected Functionality:** Template rendering engine.
* **Criticality:** MEDIUM.

### `test_lms_mapper.py` & `test_lms_client.py`
* **Purpose:** Validates LMS JSON schemas and translation to Frappe DocTypes.
* **Protected Functionality:** LMS Integration.
* **Retention:** Keep.

---

## 2. Integration / Flow Tests

### `test_e2e_campaign.py`
* **Purpose:** Simulates an entire Campaign lifecycle from `Draft` to `Queued` to `Sent`.
* **Protected Functionality:** `tasks/scheduler.py` dispatch logic.
* **Criticality:** HIGH. Modifying this test requires updating the `FOR UPDATE SKIP LOCKED` mock mechanisms.

### `test_e2e_glific_bq_flow.py`
* **Purpose:** Verifies that a Glific mock payload maps completely through Frappe down to the BigQuery executor and returns flat JSON.
* **Retention:** Keep.

### `test_glific_client.py`
* **Purpose:** Tests raw HTTP/GraphQL boundaries against Glific.
* **Criticality:** HIGH. Validates exponential backoff and timeout logic.

### `test_duplicate_dispatch.py`
* **Purpose:** Validates idempotency keys (`idempotency_key`) to prevent spamming users.
* **Protected Functionality:** Dispatch engine locks.
* **Criticality:** CRITICAL. DO NOT remove.

### `test_webhook_processor.py`
* **Purpose:** Simulates batching logic for Delivery/Read receipts.
* **Criticality:** MEDIUM.

---

## 3. Specialized Behavior Tests

### `test_falsy_sync.py` & `test_zombie_campaign.py`
* **Purpose:** Handles edge cases where campaigns are abandoned or sync jobs return null.
* **Retention:** Keep.

### `test_phase_a_fixes.py`
* **Purpose:** Regression suite for previously identified production bugs.
* **Criticality:** HIGH. Prevents regression of known data issues.

---

## 4. Testing Coverage Matrix

| Service | Covered By |
|---------|------------|
| `api.glific_bq_webhook` | `test_glific_bq_webhook.py`, `test_e2e_glific_bq_flow.py` |
| `services.bigquery_executor` | `test_bigquery.py`, `test_e2e_glific_bq_flow.py` |
| `services.redis_utils` | `test_redis_utils.py`, `test_e2e_campaign.py` |
| `tasks.scheduler` | `test_e2e_campaign.py`, `test_duplicate_dispatch.py` |
| `services.glific_client` | `test_glific_client.py`, `test_hsm_fallback.py` |
| `services.lms_ingestion` | `test_lms_ingestion.py` |
| `services.lms_student_sync` | `test_lms_student_sync.py` |
