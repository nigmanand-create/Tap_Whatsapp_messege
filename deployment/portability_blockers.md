# Portability Blockers & Remediation Report

This report serves as the definitive list of dependency failures blocking the deployment and portability of the TAP Buddy application.

## 1. The Blocker Audit

### Missing Database Schemas
The following core structural tables are required by the application code, but their JSON definitions are completely missing from the Git repository:
- `WhatsApp Group`
- `WhatsApp Group Collection`
- `WhatsApp Group Collection Mapping`

**Status:** `NOT TRACKED IN GIT`
**Reason:** During initial development via the Frappe UI, the `Custom?` checkbox was explicitly enabled (`custom=1`) on these DocTypes. Frappe's architecture intentionally prevents custom DocTypes from exporting to the filesystem to prevent overriding user-specific site tweaks.

### Missing UI Enhancements
- `Workspace` (The TAP Buddy sidebar navigation)
- `Property Setter` (Configurations hiding the raw tables from standard users)

**Status:** `NOT TRACKED IN GIT`
**Reason:** Workspaces and Property Setters are inherently database-bound unless explicitly declared as `fixtures` inside `hooks.py` to trigger their export.

---

## 2. Dependency Cascade (Why it breaks)

Because `WhatsApp Group` is missing from the file system, Frappe's native `install-app` orchestrator will crash when evaluating the following JSON files that we *did* commit:

- `Campaign Recipient.json` -> Links to `WhatsApp Group`
- `Dispatch Attempt.json` -> Links to `WhatsApp Group`
- `Message Log.json` -> Links to `WhatsApp Group`
- `TAP Campaign.json` -> Links to `WhatsApp Group` and `WhatsApp Group Collection`

**Exact Failure Point:**
```python
Traceback (most recent call last):
  File "frappe/model/sync.py", line 124, in sync
    raise frappe.exceptions.DoesNotExistError(f"DocType {target_doctype} not found")
```

---

## 3. Required Remediation Strategy

To unlock deployment and make the Docker container functional, the developer must perform the following explicit schema conversion against their local developer database *before* publishing the next commit:

### Step 1: Convert Custom DocTypes to Standard App DocTypes
You must uncheck the `Custom` flag and lock the DocTypes to the module. This can be done via `bench console`:
```python
for dt in ["WhatsApp Group", "WhatsApp Group Collection", "WhatsApp Group Collection Mapping"]:
    doc = frappe.get_doc("DocType", dt)
    doc.custom = 0
    doc.module = "TAP Buddy"
    doc.save()
```
*This action will physically generate the missing `.json`, `.py`, and `.js` folders inside `apps/tap_buddy/tap_buddy/tap_buddy/doctype/`.*

### Step 2: Export Workspaces and UI Tweaks
Add the following array to `apps/tap_buddy/tap_buddy/hooks.py`:
```python
fixtures = [
    {"dt": "Workspace", "filters": [["name", "=", "TAP Buddy"]]},
    {"dt": "Property Setter", "filters": [["doc_type", "in", ["WhatsApp Group", "WhatsApp Group Collection", "WhatsApp Group Collection Mapping"]]]}
]
```
Then run:
```bash
bench export-fixtures
```

### Step 3: Commit and Deploy
Once those missing folders and `fixtures/` directories appear in your git status, commit them to `feature/whatsapp-group-integration`. At that point, the Docker stack and fresh installations will reach 100% portability.
