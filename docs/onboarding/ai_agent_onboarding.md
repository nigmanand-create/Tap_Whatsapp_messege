# AI Agent Onboarding Guide

## Repository Orientation
This is a high-throughput async processing hub bridging LMS, Frappe, BigQuery, and Glific. It uses strict table locking and Redis rate limits to prevent provider bans.

## Things You Must Never Change Without Understanding
- **FOR UPDATE SKIP LOCKED:** Found in `db_utils.py`. Used by the scheduler to pull campaign recipients safely. Modifying this introduces race conditions.
- **Redis Token Bucket:** Found in `redis_utils.py`. The Glific GraphQL API bans aggressively. The dispatcher strictly adheres to this limit.
- **Webhook Formats:** Webhooks MUST strip Frappe's `{"message"}` wrapper via `frappe.response.update()`.

## Dangerous Files
- `scheduler.py`: Do not edit dispatch windows or token consumers blindly.
- `db_utils.py`: Contains raw PostgreSQL queries to bypass Frappe ORM limits for performance.

## Safe Modification
Always refer to:
- [Change Impact Matrix](../analysis/CHANGE_IMPACT_MATRIX.md)
- [Runtime Execution Maps](../analysis/RUNTIME_EXECUTION_MAPS.md)
- [Testing Reference](../analysis/TESTING_REFERENCE.md)
- [Scheduler Reference](../analysis/SCHEDULER_REFERENCE.md)
