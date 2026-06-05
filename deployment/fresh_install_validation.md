# Fresh Installation Validation Audit

This document traces the exact lifecycle and predicted outcome of a brand-new developer attempting to clone the repository, boot the Docker infrastructure, and install the TAP Buddy application.

## 1. Repository Clone & Build Phase
**Action:** Developer runs `git clone` and `docker-compose up -d --build`.
**Result:** **SUCCESS**
- The repository clone cleanly pulls the application code.
- The `Dockerfile` successfully builds the custom image, fetching Frappe v16 and installing `tap_buddy` into the python virtual environment.
- The Postgres database and Redis caches initialize correctly.

## 2. Infrastructure Boot Phase
**Action:** Services achieve `healthy` status.
**Result:** **SUCCESS**
- Gunicorn web workers mount port `8000`.
- SocketIO mounts port `9000`.
- RQ workers (`queue-long`, `queue-short`, `queue-default`) successfully connect to the Redis instance and await jobs.

## 3. Application Installation Phase
**Action:** Developer executes `bench new-site tapbuddy.local` followed by `bench --site tapbuddy.local install-app tap_buddy`.
**Result:** **CRITICAL FAILURE**
- Site creation succeeds, generating a clean Postgres database.
- `install-app` begins parsing `.json` schema files in the `apps/tap_buddy` repository.
- **Failure Point:** When Frappe evaluates `Campaign Recipient.json`, it parses the `whatsapp_group` Link field. It searches the codebase for the `WhatsApp Group` schema definition.
- **Exception Thrown:** `frappe.exceptions.DoesNotExistError: DocType WhatsApp Group not found`.
- The database migration immediately aborts, leaving the site completely broken.

## 4. Post-Install Feature Validations
*(These steps are technically unreachable due to the Phase 3 crash, but are evaluated hypothetically assuming a bypassed installation)*
- **Scheduler Startup:** Fails. Dependencies in `scheduler.py` relying on `WhatsApp Group Collection Mapping` will crash during background execution.
- **WhatsApp Group Browser:** Fails to load. The Vue SPA depends on the backend `get_whatsapp_groups` API, which will throw a SQL `Table Doesn't Exist` error.
- **Campaign Engine:** Fails to load. The UI relies on link validations to the missing `WhatsApp Group` doctype.
- **Group Collection Sync:** Fails entirely.

## Conclusion
The Docker environment boots perfectly, but the Frappe schema installation completely blocks deployment. The codebase is currently non-portable.
