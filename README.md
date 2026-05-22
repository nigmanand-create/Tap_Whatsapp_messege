### TAP Buddy

WhatsApp Automation Platform

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app tap_buddy
```

### Configuration

#### TAP Buddy Settings
- Configure `glific_url` and `glific_token` when you have API access.
- Configure webhook settings if using Glific callbacks: `webhook_enabled`, `webhook_secret`, and `webhook_signature_header`.

### Workflow (Queue-First)

Canonical flow:

1) Campaign Created (Draft)
2) Campaign Submitted (Scheduled)
3) Dispatcher builds recipients and message logs during dispatch
4) Messages sent
5) Webhook updates delivery/read status

Note: Recipient creation and Message Log creation happen during dispatch, not on submit.

#### LMS Integration Settings
- Enable LMS integration and set `webhook_secret` + `webhook_signature_header`.
- If polling is enabled, set `lms_base_url` and `lms_api_key`.

#### Glific Sync Settings
- Enable sync only when ready. Use `dry_run=1` until API credentials are available.
- Set `sync_only_new=1` to use incremental syncing based on `last_synced_at`.

### Webhooks

#### Glific webhook
- Endpoint: `/api/method/tap_buddy.api.webhook.handle`
- Required header: `X-Glific-Signature` (or the configured header)
- Signature: `sha256=<hex>` over raw request body using `webhook_secret`
- Required fields in payload: `provider_message_id` and `status`

#### LMS webhook
- Endpoint: `/api/method/tap_buddy.api.lms_webhook.handle`
- Required header: `X-LMS-Signature` (or the configured header)
- Signature: `sha256=<hex>` over raw request body using `webhook_secret`
- Required fields in payload: `event_type` (optional `event_id` for dedupe)

### LMS Event Mapping

Create LMS mappings in **LMS Event Mapping**:
- `event_type`: LMS event name (e.g., `program.enrolled`)
- `action`: `Log Only` or `Create Campaign`
- `template`: WhatsApp Template for `Create Campaign`
- `targeting_type`: `Single School` or `School Group`
- `school_name_key` or `school_group_key` for payload mapping

### Glific Sync

Configure **Glific Field Mapping** and **Glific Contact Group Mapping**:
- Field mapping maps `School` fields to Glific contact fields.
- Group mapping maps a `School Group` to a Glific group id.

Run sync via scheduler (`process_glific_sync`) or manually:

```bash
bench --site <site> execute tap_buddy.tasks.scheduler.process_glific_sync
```

### Operational Tools

#### Replay failed events (System Manager only)
- Webhook: `/api/method/tap_buddy.api.replay.replay_webhook`
- LMS: `/api/method/tap_buddy.api.replay.replay_lms`
- Bulk replay: `/api/method/tap_buddy.api.replay.replay_failed_webhooks` and `replay_failed_lms`

#### Metrics summary (System Manager only)
- `/api/method/tap_buddy.api.metrics.get_summary`

### Testing

Run the full test suite:

```bash
bench --site <site> run-tests --app tap_buddy
```

Run specific doctypes:

```bash
bench --site <site> run-tests --app tap_buddy --doctype "TAP Campaign"
bench --site <site> run-tests --app tap_buddy --doctype "Webhook Event"
bench --site <site> run-tests --app tap_buddy --doctype "LMS Event Mapping"
```

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/tap_buddy
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit

### Set Glific credentials from environment (recommended)

You can set sensitive Glific credentials via environment variables and apply them to the site without committing secrets:

```bash
# export the values in your shell (do NOT commit these)
export GLIFIC_URL="https://api.glific.example/v1"
export GLIFIC_TOKEN="long-primary-token"
export GLIFIC_ACCESS_TOKEN="short-lived-access-token"
export GLIFIC_REFRESH_TOKEN="refresh-token"
export GLIFIC_TOKEN_EXPIRY="2026-06-01T00:00:00"
export GLIFIC_PHONE_NUMBER="+919999999999"
export WEBHOOK_SECRET="super-secret"

# apply to site (run from bench directory)
bench --site tapbuddy.local execute "import tap_buddy.scripts.set_glific_settings as s; s.set_from_env()"
```

Alternatively you can run a one-liner with `frappe.get_single` in bench console to set specific fields.

### Run a Glific send test

1) Copy `.env.sample` to `apps/tap_buddy/.env.local` and fill values. Keep this file private.

2) By default `DRY_RUN=1` in `.env.local`. To perform a live send, set `DRY_RUN=0` and ensure `GLIFIC_TEST_PHONE` is a number you control.

3) From the bench directory run:

```bash
./apps/tap_buddy/scripts/run_glific_test.sh
```

This will execute `send_from_env()` inside the site and print the response. The script will abort if `.env.local` is missing.
