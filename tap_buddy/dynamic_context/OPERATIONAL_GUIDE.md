# Dynamic Context Engine: Operational & Administrator Guide

## Overview
The **Dynamic Context Engine** (`tap_buddy.dynamic_context`) is an isolated plug-in architecture built to resolve BigQuery Table-Valued Functions (TVFs) and manual configuration defaults for Glific WhatsApp flows.

---

## 1. How to Create a New Flow Configuration

Administrators can configure new flows directly from the Frappe Desk UI without writing code:

1. Navigate to **TAP Buddy Workspace** $\rightarrow$ click **Dynamic Context Flow Config** card.
   *(Note: If typing "Dynamic Context Flow Config" into the global search bar returns "No Results found", access directly via the Workspace sidebar card. Global search indexing requires `bench --site tapbuddy.local migrate`).*
2. Click **Add Dynamic Context Flow Config**.
3. Fill in mandatory top-level metadata:
   - **Flow ID / Code**: `onboarding_v1` *(Unique string matching your Glific webhook request)*
   - **Flow Name**: `Student Onboarding Welcome Flow`
   - **Flow Category**: Select `onboarding`
   - **Is Active**: Checked (`1`)
   - **BigQuery TVF Routine Name**: `get_onboarding_context_v1`
   - **Cache TTL (Seconds)**: `300`
   - **Bypass Cache**: Unchecked (`0`)
4. In the **Requested Fields Configuration** child table, add these rows:
   - Row 1: Field Name: `school_name` | Source: `Payload` | Is Required: Checked (`1`)
   - Row 2: Field Name: `registration_count` | Source: `BigQuery` | Is Required: Unchecked (`0`) | Default Value: `0`
   - Row 3: Field Name: `registration_link` | Source: `Manual Default` | Is Required: Unchecked (`0`) | Default Value: `https://tap.example.com/register`
5. Click **Save**.

---

## 2. How to Connect it in Glific

Inside the Glific Flow Builder (`https://glific.<yourdomain>.org`):

1. Create a **Call Webhook** action node.
2. Set **URL** to: `https://tapbuddy.example.com/api/method/tap_buddy.dynamic_context.api.handle`
3. Set **Method** to `POST`.
4. Configure JSON Payload Body:
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
5. In subsequent message nodes, reference returned variables directly:
```text
Welcome to TAP, @contact.name!
We confirmed your school is @results.call_webhook.context.school_name.
Your registration count is @results.call_webhook.context.registration_count.
Access your portal: @results.call_webhook.context.registration_link
```

---

## 3. How to Create a New BigQuery TVF

Create standard Table-Valued Functions in your BigQuery dataset (`glific_runtime_api`) accepting `phone` and parameter arguments:

```sql
CREATE OR REPLACE TABLE FUNCTION `glific_runtime_api.get_onboarding_context_v1`(
  phone STRING,
  school_name STRING
) AS (
  SELECT 
    t.student_name,
    COUNT(e.id) AS registration_count
  FROM `raw_dataset.students` t
  LEFT JOIN `raw_dataset.enrollments` e ON e.student_id = t.id
  WHERE t.phone_number = phone AND t.school = school_name
  GROUP BY t.student_name
);
```

---

## 4. Required Webhook Payload Format

| Field | Type | Required | Description | Example Value |
| :--- | :--- | :---: | :--- | :--- |
| `secret` | String | Yes | Auth token matching TAP Buddy Settings. | `"vertical_secure_secret"` |
| `flow_id` | String | Yes* | Mapped Flow ID definition. | `"onboarding_v1"` |
| `flow_category` | String | Yes* | Category fallback code. | `"onboarding"` |
| `contact.phone`| String | Yes | Recipient phone number. | `"919876543210"` |
| `parameters` | Object | No | Key-value pairs passed to TVF. | `{"school": "KV Pune"}` |
| `bypass_cache` | Int | No | Send `1` to force fresh SQL execution. | `0` |

---

## 5. Cache Behavior & Determinism

Cache keys are SHA-256 collision-resistant strings generated deterministically:
`dyn_ctx:v1:<flow_id>:<phone>:<sha256(json.dumps(parameters))>:<mock_mode>`

* **MISS**: Executes BigQuery SQL, caches flat dict in Redis for configured TTL (`300s`).
* **HIT**: Returns Redis dict immediately (~0.6ms latency).
* **BYPASS**: Skips Redis cache when `bypass_cache=1` or `mock_mode=1`.

---

## 6. Standard Error Response Format

Every failure returns a standardized flat JSON schema with HTTP error status codes:

```json
{
  "success": false,
  "error": "Missing required field: school_name mapped from Payload",
  "error_code": "VALIDATION_FAILED",
  "correlation_id": "dyn-err-88a1b2c3",
  "timestamp": "2026-06-26T06:25:00Z"
}
```

---

## 7. Troubleshooting & Common Errors

| Error Code | HTTP Status | Root Cause | Remediation |
| :--- | :--- | :--- | :--- |
| `UNAUTHORIZED` | 401 | Secret token mismatch. | Check `webhook_secret` in Desk $\rightarrow$ TAP Buddy Settings. |
| `FLOW_NOT_FOUND` | 404 | Unmapped `flow_id` and category. | Ensure DocType record exists and `is_active=1`. |
| `VALIDATION_FAILED`| 400 | Missing mandatory child field. | Check Glific contact profile variables passed in body. |
| `PROVIDER_FAILED` | 500 | BigQuery routine timed out (>15s). | Optimize SQL query or add clustering on `phone`. |

---

## 8. Deployment Guide (Exact Commands)

Execute these literal terminal commands to deploy or update the module on local or production sites:

### Local Development Site (`tapbuddy.local`)
```bash
cd /Users/blackstar/dev/client/tap-bench
bench --site tapbuddy.local migrate
bench clear-cache
bench restart
```

### Production Environment (`tapbuddy.prod`)
```bash
cd ~/tap-bench
git pull origin dev
bench --site tapbuddy.prod migrate
bench clear-cache
bench restart
```

---

## 9. Final Verification Checklist

Before signing off deployment, confirm every item below is operational:

- [ ] **Endpoint Reachable**: `/api/method/tap_buddy.dynamic_context.api.handle` responds to HTTP POST.
- [ ] **Authentication Works**: Invalid secret returns HTTP 401 Unauthorized.
- [ ] **Flow Config Found**: DocType flow record loads cleanly from database registry.
- [ ] **BigQuery Returns Data**: `execute_tvf` executes mapped routine without timeout.
- [ ] **Cache Works**: Second identical request returns cache HIT (~0.6ms).
- [ ] **Glific Receives Context**: Flat JSON structure consumed by Glific webhook node.
- [ ] **WhatsApp Message Renders Correctly**: Flow template renders all `@results` variables.
- [ ] **Existing TAP Buddy Functionality Unaffected**: All legacy schedulers operate with zero regressions.
