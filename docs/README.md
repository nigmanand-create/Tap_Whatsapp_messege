# TAP Buddy

## System Overview
TAP Buddy is the middleware bridge between the Learning Management System (LMS), Google BigQuery, and Glific (WhatsApp). It synchronizes LMS student data, runs messaging campaigns, and serves real-time BigQuery context via webhooks to Glific flows.

## Core Architecture
- **Frappe Framework:** Provides PostgreSQL ORM, UI, and Redis-backed task queuing.
- **LMS Sync Engine:** Custom asynchronous parsers pulling assignments and enrollments.
- **Campaign Dispatcher:** Scalable WhatsApp dispatcher with token-bucket rate limiting.

## Documentation Index
- [Architecture Details](ARCHITECTURE.md)
- [System Execution Flows](SYSTEM_FLOWS.md)
- [Deployment Architecture](DEPLOYMENT.md)
- [Operations Runbook](OPERATIONS_RUNBOOK.md)
- [AI Agent Onboarding Guide](AI_AGENT_GUIDE.md)

### Detailed Catalogs
- [Domain Model](architecture/domain_model.md)
- [Service Catalog](architecture/service_catalog.md)
- [API Catalog](architecture/api_catalog.md)

### Analysis Artifacts
- [Change Impact Matrix](analysis/CHANGE_IMPACT_MATRIX.md)
- [Runtime Execution Maps](analysis/RUNTIME_EXECUTION_MAPS.md)
- [Scheduler Reference](analysis/SCHEDULER_REFERENCE.md)
- [Testing Reference](analysis/TESTING_REFERENCE.md)
