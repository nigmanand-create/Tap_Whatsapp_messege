# WGAS — WhatsApp Group Automation System

WGAS turns a monthly Excel sheet into scheduled WhatsApp **group** messages and **Glific flows**, then tracks delivery and responses.

## Excel format

| date | time | whatsapp group / groups | message | flow |
|------|------|-------------------------|---------|------|
| 2026-10-05 | 09:30 | School A Group, School B Group | Hello parents | |
| 2026-10-06 | 14:00 | Block 3 Teachers | | Attendance Flow |

- **date** + **time**: when the send should run (plan timezone, default `Asia/Kolkata`).
- **groups**: one or more group names separated by `,` `;` `|` or new lines. Names must match synced **WhatsApp Group** records (run group sync from TAP Buddy first).
- **message**: plain text to the group (optional if **flow** is set).
- **flow**: Glific flow name or ID (optional if **message** is set). Must exist in **Glific Flow** (sync flows daily or from Desk).

## Desk workflow

1. Open **WGAS** page or **WGAS Plan**.
2. Create a plan, attach Excel, click **Import Excel**.
3. Review child rows (one row per group per Excel line).
4. Click **Create Scheduled Campaigns** — creates **TAP Campaign** per row with `send_date` set; worker fires at time via existing scheduler.
5. **Refresh Engagement** (or wait for cron) for delivery + poll/flow response counts.

## Settings

**WGAS Settings** — Glific URL, login phone, tokens (same as TAP Buddy Settings; save here syncs to TAP Buddy). Use **Bootstrap Glific**, **Test Connection**, **Sync WhatsApp Groups**, and **Sync Glific Flows** from the form toolbar.

## Requirements

- `bench start` (Redis + workers + scheduler)
- Glific credentials in **TAP Buddy Settings**
- Webhooks enabled for delivery/read updates on group messages
