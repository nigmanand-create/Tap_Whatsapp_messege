# TAP Buddy Docker Deployment Guide

> [!WARNING]
> **Reference Only & Portability Constraint**
> The Docker assets provided in this directory (`Dockerfile`, `docker-compose.yml`) are meant as **documentation and reference templates**. 
> 
> Due to the current architecture, some core database schemas (such as `WhatsApp Group`) exist *only* in the production database and are not tracked in Git. Therefore, attempting a "fresh install" of this repository onto a brand-new database using these Docker files will currently fail. 
> 
> **To deploy a new environment, you must restore a database backup from production first.** Please refer to the [Backup and Recovery Guide](backup_and_recovery.md).

This guide provides instructions on how to structure a Docker deployment for TAP Buddy, isolated from local bench environments.

## Local Development Setup

1. **Clone the Repository**
   ```bash
   git clone git@github.com:nigmanand-create/Tap_Whatsapp_messege.git apps/tap_buddy
   cd apps/tap_buddy/deployment
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env and provide your Database passwords, Glific API keys, and LMS keys.
   ```

3. **Start the Infrastructure**
   ```bash
   docker-compose up -d
   ```
   *This will boot Postgres, Redis, Frappe web workers, background queues, and the scheduler.*

4. **Install the Application onto the Site**
   Wait for the containers to fully initialize, then run:
   ```bash
   docker-compose exec backend bench new-site tapbuddy.local \
     --db-type postgres \
     --db-root-password your_db_password \
     --admin-password admin
   
   docker-compose exec backend bench --site tapbuddy.local install-app tap_buddy
   ```

5. **Enable the Scheduler**
   ```bash
   docker-compose exec backend bench --site tapbuddy.local enable-scheduler
   ```

6. **Verify Services**
   - Access the site at `http://localhost:8080` (or your configured port).
   - Login as `Administrator` using the password you set.
   - Navigate to **TAP Buddy Settings** and verify that LMS and Glific configurations are loaded.

## Production Setup Guidelines

For production environments, do not use the development `docker-compose.yml` directly without a reverse proxy (like Traefik or Nginx proxy manager) providing SSL termination. 

**Production Checklist:**
- [ ] Change `DB_PASSWORD` to a highly secure randomly generated string.
- [ ] Ensure `DRY_RUN=0` in `.env`.
- [ ] Set up daily database backups using `bench backup` wrapped in a cron job targeting the `backend` container.
- [ ] Monitor the `queue-long` worker logs, as WhatsApp Campaign Dispatches utilize this queue for execution.
