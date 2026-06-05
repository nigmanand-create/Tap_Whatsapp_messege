# TAP Buddy Backup & Recovery Guide

This document outlines the standard operating procedures for safeguarding and restoring the TAP Buddy production database. 

> [!WARNING]
> **Schema Source of Truth**
> Currently, the core `WhatsApp Group` schemas exist exclusively within the production database, not in the Git repository. Therefore, **taking regular database backups is the only way to prevent catastrophic data and schema loss.**

---

## 1. Automated Backups (Recommended)

Frappe has built-in automated backup capabilities. It is highly recommended to rely on Frappe's native scheduler.

### Enable Automated Backups
1. Log into the Frappe Desk as `Administrator`.
2. Navigate to **System Settings**.
3. Under the **Backups** section, ensure `Backups` are enabled and set to the desired frequency (Daily/Weekly).
4. *(Optional but Recommended)* Configure **S3 Backup** in the integrations module to automatically push the `.sql.gz` dumps to an offsite AWS/DigitalOcean bucket.

---

## 2. Manual Backup (Ad-hoc)

If you need to snapshot the database before a major migration or deployment, you can trigger a manual backup using the bench CLI.

### Standard Bench Setup
Run this command from the `tap-bench` root folder:
```bash
bench --site tapbuddy.local backup --with-files
```
- The database dump will be stored in `sites/tapbuddy.local/private/backups/`.
- The `--with-files` flag ensures all uploaded PDFs, images, and attachments are also backed up.

### Dockerized Setup
If running via the reference Docker Compose stack:
```bash
docker-compose exec backend bench --site tapbuddy.local backup --with-files
```

---

## 3. Disaster Recovery (Restoration)

If the database becomes corrupted or you need to clone the production database to a staging environment, follow this procedure.

### Step 1: Locate the Backup
Identify the exact SQL file you wish to restore from the `private/backups/` folder. It will look like: `20260605_123456_tapbuddy_database.sql.gz`.

### Step 2: Restore the Database
Run the following command from the `tap-bench` directory, replacing the path with your specific backup file:
```bash
bench --site tapbuddy.local restore sites/tapbuddy.local/private/backups/20260605_123456_tapbuddy_database.sql.gz
```

### Step 3: Restore Public/Private Files (If applicable)
If you also need to restore file uploads (attachments), pass the tarballs during the restore command:
```bash
bench --site tapbuddy.local restore sites/tapbuddy.local/private/backups/20260605_123456_tapbuddy_database.sql.gz \
  --with-public-files sites/tapbuddy.local/private/backups/20260605_123456_tapbuddy_files.tar \
  --with-private-files sites/tapbuddy.local/private/backups/20260605_123456_tapbuddy_private_files.tar
```

### Step 4: Run Migrations
Always run migrations after a restore to ensure the database schema aligns with the current codebase:
```bash
bench --site tapbuddy.local migrate
```

---

## 4. Emergency Database Access
If the Frappe application completely fails to boot, you can access the underlying PostgreSQL database directly:

```bash
# Dockerized access
docker-compose exec db psql -U postgres -d tapbuddy

# Local bench access (using frappe credentials)
bench --site tapbuddy.local mariadb  # (or psql if on postgres)
```
