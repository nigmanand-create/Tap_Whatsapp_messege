# Docker Deployment Requirements Audit

## 1. System Requirements
- **Python Version:** 3.11+ (Required by Frappe v16 Docker standard images)
- **Node Version:** 18+ (Required by Frappe v16 asset compiler)
- **Frappe Version:** v16 (`v16.18.2` or later on the `version-16` branch)

## 2. Infrastructure Requirements
- **Database:** PostgreSQL (Frappe is explicitly configured for `db_type: postgres` on this project)
- **Cache & Queue:** Redis (3 separate instances or logical databases: cache, queue, socketio)
- **Proxy:** Nginx (For asset serving and reverse proxying gunicorn/socketio)
- **Workers:** Gunicorn backend (web), RQ background workers (`short`, `default`, `long`)

## 3. Required Environment Variables
To successfully deploy the TAP Buddy stack, the following credentials must be provided via a secure `.env` file at runtime (no secrets should be baked into the image):

### 3.1 Frappe & Database Configuration
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `REDIS_CACHE`, `REDIS_QUEUE`, `REDIS_SOCKETIO`
- `FRAPPE_SITE_NAME_HEADER`

### 3.2 TAP Buddy External Integrations
**Glific Configuration:**
- `GLIFIC_URL` (Base URL for Glific API)
- `GLIFIC_TOKEN` / `GLIFIC_ACCESS_TOKEN` / `GLIFIC_REFRESH_TOKEN` / `GLIFIC_TOKEN_EXPIRY`
- `GLIFIC_PHONE_NUMBER`
- `WEBHOOK_SECRET`

**LMS Configuration:**
- `LMS_BASE_URL`
- `LMS_API_KEY`
- `LMS_POLLING_ENABLED` (Boolean/Integer)

## 4. Local Developer Tooling
Developers must have `docker` and `docker-compose` installed. Local setups should utilize volume mounts (`frappe-sites`, `frappe-logs`) to preserve databases and site assets across container restarts.
