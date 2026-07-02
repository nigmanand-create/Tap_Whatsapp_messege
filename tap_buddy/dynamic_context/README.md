# Dynamic Context Engine: Developer & Administrator End-to-End Testing Guide

This document is the authoritative developer and administrator reference for verifying, configuring, testing, deploying, and maintaining the **Dynamic Context Engine** (`tap_buddy.dynamic_context`). 

The Dynamic Context Engine is an isolated plug-in module built to dynamically resolve BigQuery Table-Valued Functions (TVFs) and manual configuration defaults for Glific WhatsApp flows.

---

## 1. Prerequisites

### System & Framework Stack
* **OS**: macOS / Linux (Ubuntu/Debian)
* **Bench Version**: Frappe Bench CLI v5.x+
* **Python Version**: Python 3.11 - 3.14+
* **Frappe Version**: Frappe Framework v15.x / v16.x / v17.x
* **App Root**: `/Users/blackstar/dev/client/tap-bench/apps/tap_buddy`

### Required Environment Variables & Services
* **Redis Cache Service**: Must be actively running (`redis://localhost:13000` or managed by bench) to support SHA-256 caching.
* **MariaDB / MySQL**: Active database engine for Frappe DocTypes.
* **Google Cloud GCP Auth**: `GOOGLE_APPLICATION_CREDENTIALS` environment variable pointing to active service account JSON (required if executing live non-mocked BigQuery routines).

### Required Frappe DocTypes
Installed automatically via module sync:
1. `Dynamic Context Flow Config` (Parent configuration mapping)
2. `Dynamic Context Flow Field` (Child table field specifications)
3. `Dynamic Context Audit Log` (Immutable non-blocking execution trail)

### Required Settings Configuration
* **TAP Buddy Settings**: Must have `webhook_secret` populated (e.g., `vertical_secure_secret`).
* **TAP BigQuery Settings**: Must have GCP Project ID and Dataset configured.

---

## 2. Installation

Open your terminal and execute the following commands in order to boot the bench environment:

```bash
cd /Users/blackstar/dev/client/tap-bench
bench start
```

*(Leave `bench start` running in terminal tab 1. Open terminal tab 2 for subsequent commands).*

---

## 3. Migration

Install and sync the new database tables and Desk workspace cards into your active site (`tapbuddy.local`):

```bash
cd /Users/blackstar/dev/client/tap-bench
bench --site tapbuddy.local migrate
bench clear-cache
bench clear-website-cache
```

Restart background web workers to ensure Python module memory registries reload cleanly:

```bash
bench restart
```

---

## 4. Configuration

### Step A: Configure TAP Buddy Secret
1. Open Frappe Desk UI (`http://tapbuddy.local:8000`).
2. Search for **TAP Buddy Settings**.
3. Set **Webhook Secret** to: `vertical_secure_secret`
4. Click **Save**.

### Step B: Configure BigQuery Settings
1. Navigate to **TAP Buddy Workspace** $\rightarrow$ **Configuration** card $\rightarrow$ click **TAP BigQuery Settings**.
   *(Note: If typing "TAP BigQuery Settings" into the global search bar returns "No Results found", navigate directly via the Workspace sidebar card. Global search indexing requires `bench --site tapbuddy.local migrate` to register newly added DocTypes).*
2. Ensure **Project ID** (`api_project_prod`) and **Default Dataset** (`api_dataset`) are populated.

---

## 5. Create a Sample Flow

Create a complete onboarding configuration directly from the Desk UI or via Python CLI:

1. Navigate to **TAP Buddy Workspace** $\rightarrow$ **Dynamic Context Flow Config**.
2. Click **Add Dynamic Context Flow Config**.
3. Configure top-level metadata:
   - **Flow ID / Code**: `onboarding_v1`
   - **Flow Name**: `Student Onboarding Welcome Flow`
   - **Flow Category**: `onboarding`
   - **Is Active**: Checked (`1`)
   - **BigQuery TVF Routine Name**: `get_onboarding_context_v1`
   - **Cache TTL (Seconds)**: `300`
   - **Bypass Cache**: Unchecked (`0`)
4. In the **Requested Fields Configuration** child table, add these 3 rows:
   - Row 1: Field Name: `school_name` | Source: `Payload` | Is Required: Checked (`1`)
   - Row 2: Field Name: `registration_count` | Source: `BigQuery` | Is Required: Unchecked (`0`) | Default Value: `0`
   - Row 3: Field Name: `registration_link` | Source: `Manual Default` | Is Required: Unchecked (`0`) | Default Value: `https://tap.example.com/register`
5. Click **Save**.

---

## 6. Testing the API

Copy and paste these ready-to-use `curl` terminal commands to verify all 6 core API execution paths against `http://127.0.0.1:8000`:

### 1. Successful Request (`HTTP 200 OK`)
```bash
curl -i -X POST http://tapbuddy.local:8000/api/method/tap_buddy.dynamic_context.api.handle \
-H "Content-Type: application/json" \
-d '{
  "request_id": "req-test-success-001",
  "secret": "vertical_secure_secret",
  "flow_id": "onboarding_v1",
  "flow_category": "onboarding",
  "contact": {
    "phone": "919876543210",
    "name": "Sunita Rao"
  },
  "school_name": "KV Ganeshkhind Pune",
  "mock_mode": 1
}'
```

### 2. Invalid Secret Token (`HTTP 401 Unauthorized`)
```bash
curl -i -X POST http://tapbuddy.local:8000/api/method/tap_buddy.dynamic_context.api.handle \
-H "Content-Type: application/json" \
-d '{
  "request_id": "req-test-auth-fail",
  "secret": "WRONG_SECRET_TOKEN",
  "flow_id": "onboarding_v1",
  "contact": { "phone": "919876543210" }
}'
```

### 3. Missing Mandatory Field (`HTTP 400 Bad Request`)
```bash
curl -i -X POST http://tapbuddy.local:8000/api/method/tap_buddy.dynamic_context.api.handle \
-H "Content-Type: application/json" \
-d '{
  "request_id": "req-test-missing-field",
  "secret": "vertical_secure_secret",
  "flow_id": "onboarding_v1",
  "contact": { "phone": "919876543210" }
}'
```
*(Fails because mandatory `school_name` mapped from Payload is omitted).*

### 4. Unknown Flow ID (`HTTP 404 Not Found`)
```bash
curl -i -X POST http://tapbuddy.local:8000/api/method/tap_buddy.dynamic_context.api.handle \
-H "Content-Type: application/json" \
-d '{
  "request_id": "req-test-404",
  "secret": "vertical_secure_secret",
  "flow_id": "ghost_flow_v99",
  "contact": { "phone": "919876543210" }
}'
```

### 5. Force Bypass Cache (`bypass_cache=1`)
```bash
curl -i -X POST http://tapbuddy.local:8000/api/method/tap_buddy.dynamic_context.api.handle \
-H "Content-Type: application/json" \
-d '{
  "request_id": "req-test-bypass",
  "secret": "vertical_secure_secret",
  "flow_id": "onboarding_v1",
  "contact": { "phone": "919876543210" },
  "school_name": "KV Ganeshkhind Pune",
  "bypass_cache": 1,
  "mock_mode": 1
}'
```

### 6. Mock Mode Execution (`mock_mode=1`)
```bash
curl -i -X POST http://tapbuddy.local:8000/api/method/tap_buddy.dynamic_context.api.handle \
-H "Content-Type: application/json" \
-d '{
  "request_id": "req-test-mock",
  "secret": "vertical_secure_secret",
  "flow_id": "onboarding_v1",
  "contact": { "phone": "919876543210" },
  "school_name": "KV Ganeshkhind Pune",
  "mock_mode": 1
}'
```

---

## 7. Verify Cache Behavior

Execute Request #1 followed immediately by Request #2 in your terminal:

```bash
# Request 1 -> Cache MISS (~2.5ms latency)
curl -s -X POST http://tapbuddy.local:8000/api/method/tap_buddy.dynamic_context.api.handle \
-H "Content-Type: application/json" \
-d '{"request_id":"req-c-1","secret":"vertical_secure_secret","flow_id":"onboarding_v1","contact":{"phone":"919876543210"},"school_name":"KV Pune","mock_mode":1}'

# Request 2 -> Cache HIT (~0.7ms latency - Zero BigQuery calls)
curl -s -X POST http://tapbuddy.local:8000/api/method/tap_buddy.dynamic_context.api.handle \
-H "Content-Type: application/json" \
-d '{"request_id":"req-c-2","secret":"vertical_secure_secret","flow_id":"onboarding_v1","contact":{"phone":"919876543210"},"school_name":"KV Pune","mock_mode":1}'
```

### Inspecting Cache Logs
Inspect real-time Frappe background log files:
```bash
tail -n 50 /Users/blackstar/dev/client/tap-bench/logs/frappe.log
```
Expected output sequence:
```text
[INFO] [dynamic_context] [Cache MISS] dyn_ctx:v1:onboarding_v1:919876543210:...:1
[INFO] [dynamic_context] [Cache HIT] dyn_ctx:v1:onboarding_v1:919876543210:...:1
```

---

## 8. Verify BigQuery Execution

To confirm `execute_tvf()` is actually invoked inside `tap_buddy.services.bigquery_executor`:

1. Run terminal query with `bypass_cache: 1`:
```bash
curl -s -X POST http://tapbuddy.local:8000/api/method/tap_buddy.dynamic_context.api.handle \
-H "Content-Type: application/json" \
-d '{"request_id":"req-bq-trace","secret":"vertical_secure_secret","flow_id":"onboarding_v1","contact":{"phone":"919876543210"},"school_name":"KV Pune","bypass_cache":1,"mock_mode":0}'
```
2. Inspect BigQuery trace logs:
```bash
grep "get_onboarding_context_v1" /Users/blackstar/dev/client/tap-bench/logs/bigquery.log
```
3. Expected log entry:
```text
[INFO] [bigquery] Executing TVF get_onboarding_context_v1 for phone 919876543210 with params {'phone': '919876543210'}
```

---

## 9. End-to-End Glific Test Guide

Inside Glific Flow Builder (`https://glific.<yourdomain>.org`):

1. **Create Flow**: Name it `Onboarding Welcome Demo`.
2. **Add Node**: Select **Call Webhook** action type.
3. **Webhook URL**: `https://tapbuddy.example.com/api/method/tap_buddy.dynamic_context.api.handle`
4. **Headers**:
   - `Content-Type`: `application/json`
5. **Request Body** (Raw JSON):
```json
{
  "request_id": "@contact.id-@flow.uuid",
  "secret": "vertical_secure_secret",
  "flow_id": "onboarding_v1",
  "flow_category": "onboarding",
  "contact": {
    "phone": "@contact.phone",
    "name": "@contact.name"
  },
  "school_name": "@contact.fields.school_name"
}
```
6. **Subsequent Send Message Node Variables**:
```text
Welcome to TAP, @contact.name!
We confirmed your school is @results.call_webhook.context.school_name.
Your registration count is @results.call_webhook.context.registration_count.
Access your portal: @results.call_webhook.context.registration_link
```
7. **Verification**: Trigger flow via WhatsApp test device. Verify incoming message renders exact database and payload properties with zero unparsed `@results` strings.

---

## 10. Troubleshooting Reference Table

| Problem | Possible Cause | Solution |
| :--- | :--- | :--- |
| **HTTP 401 Unauthorized** | Webhook secret token mismatch. | Verify `webhook_secret` in Frappe Desk $\rightarrow$ TAP Buddy Settings. |
| **HTTP 404 Flow Not Found** | Unmapped `flow_id` and unconfigured category fallback. | Check `Dynamic Context Flow Config` list view; ensure `is_active = 1`. |
| **HTTP 400 Bad Request** | Missing mandatory field required by DocType config. | Check child table `is_required` flags vs. Glific contact profile variables. |
| **HTTP 500 Provider Failed** | BigQuery routine timed out (>15s limit). | Optimize BigQuery SQL query or verify GCP network firewall rules. |
| **Cache Not Working** | Redis server down or `bypass_cache=1` passed. | Run `bench redis-status` or check payload flags. |
| **Missing DocType Error** | Database migrations unapplied after git pull. | Run `bench --site tapbuddy.local migrate`. |
| **Endpoint Not Found (404)** | Gunicorn workers running stale Python code. | Run `bench restart` to flush Python import registries. |

---

## 11. Regression Verification

Execute automated regression test suites to guarantee zero existing production functionality was altered:

```bash
cd /Users/blackstar/dev/client/tap-bench/sites
../env/bin/pytest ../apps/tap_buddy/tap_buddy/tests/test_glific_bq_webhook.py -s
../env/bin/pytest ../apps/tap_buddy/tap_buddy/tests/test_isolated_dynamic_context.py ../apps/tap_buddy/tap_buddy/tests/test_vertical_slice_validation.py -s
```
Expected output: `11 passed in < 3.2s`.

---

## 12. Rollback Procedure

If immediate feature removal is required, execute these exact terminal commands:

```bash
cd /Users/blackstar/dev/client/tap-bench/apps/tap_buddy
git clean -fd tap_buddy/dynamic_context
git checkout dev -- tap_buddy/tap_buddy/workspace/tap_buddy/tap_buddy.json
cd /Users/blackstar/dev/client/tap-bench
bench --site tapbuddy.local migrate
bench restart
```
*(Zero broken imports remain because legacy production webhooks are completely uncoupled from this plug-in).*

---

## 13. Production VM Deployment

Execute these exact production deployment commands on your GCP / AWS virtual machine:

```bash
cd ~/tap-bench
git pull origin dev
bench --site tapbuddy.prod migrate
bench clear-cache
bench restart
```

### Production Post-Deploy Smoke Test
```bash
curl -i -X POST https://tapbuddy.prod/api/method/tap_buddy.dynamic_context.api.handle \
-H "Content-Type: application/json" \
-d '{"secret":"prod_secret"}'
# Expect HTTP 400 Bad Request with standardized flat JSON error schema
```

---

## 14. Final Verification Checklist

Before signing off deployment, confirm every item below is checked:

- [ ] **Endpoint Reachable**: `/api/method/tap_buddy.dynamic_context.api.handle` responds to HTTP POST.
- [ ] **Authentication Works**: Invalid secret returns HTTP 401 Unauthorized.
- [ ] **Flow Config Found**: DocType flow record loads cleanly from database registry.
- [ ] **BigQuery Returns Data**: `execute_tvf` executes mapped routine without timeout.
- [ ] **Cache Works**: Second identical request logs `[Cache HIT]` (~0.6ms).
- [ ] **Glific Receives Context**: Flat JSON structure consumed by Glific webhook node.
- [ ] **WhatsApp Message Renders Correctly**: Flow template renders all `@results` variables.
- [ ] **Existing TAP Buddy Functionality Unaffected**: All legacy campaign schedulers and webhooks operate with zero regressions.
