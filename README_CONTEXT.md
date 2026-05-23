# TAP Buddy - Complete Application Context

## Application Overview

**TAP Buddy** is a Frappe-based web application that manages WhatsApp-enabled educational campaigns for schools. It integrates with Glific (WhatsApp Business API platform) to send bulk messages, track student engagement, and process LMS data pipelines.

**Primary Use Case**: Schools can create campaigns to send WhatsApp messages to students, track which students opened/read messages, and schedule follow-up actions based on engagement metrics.

---

## Architecture & Tech Stack

### Backend
- **Framework**: Frappe (Python-based ERP framework)
- **Python Version**: 3.14.3 (managed via `uv`)
- **Key Libraries**:
  - `frappe`: Core framework
  - `requests`: HTTP calls to Glific API
  - `pandas`: Data processing for LMS imports
  - `celery`/`rq`: Background job queues

### Frontend
- **JavaScript Framework**: Frappe's native form handlers (vanilla JS + jQuery)
- **Build Tool**: esbuild (bundling), Webpack (Cypress preprocessing)
- **Testing**: Cypress 15.15.0 (UI tests)
- **Node Version**: 20.20.2 (managed via `nvm`)

### Data & Services
- **Database**: SQLite (site: `tapbuddy.local`)
- **Cache**: Redis (port 6379, configured in `config/redis_cache.conf`)
- **Queue**: Redis (port 6380, configured in `config/redis_queue.conf`)
- **Glific API**: WhatsApp integration service (external)

### Deployment
- **Local**: `bench` command with Frappe development server
- **Port**: 8000 (default)
- **Site URL**: `http://tapbuddy.local:8000`

---

## Project Structure

```
/Users/blackstar/dev/client/tap-bench/
├── apps/
│   ├── frappe/                          # Frappe framework repo
│   │   ├── cypress/                     # Cypress test setup
│   │   │   ├── integration/
│   │   │   │   └── tap_buddy_ui_spec.js # Main UI test spec
│   │   │   ├── plugins/
│   │   │   ├── support/
│   │   │   └── cypress.config.js
│   │   └── esbuild/                     # JavaScript bundling
│   │
│   └── tap_buddy/                       # TAP Buddy application
│       ├── tap_buddy/                   # Python package
│       │   ├── doctype/
│       │   │   ├── tap_campaign/        # Main campaign form
│       │   │   │   ├── tap_campaign.py  # Python controller
│       │   │   │   ├── tap_campaign.js  # Form handler (client-side)
│       │   │   │   └── tap_campaign.json # DocType schema
│       │   │   ├── tap_buddy_settings/  # Config DocType
│       │   │   │   ├── tap_buddy_settings.py
│       │   │   │   └── tap_buddy_settings.json
│       │   │   ├── school/              # School entity
│       │   │   │   └── school.py
│       │   │   ├── whatsapp_template/   # Message templates
│       │   │   │   └── whatsapp_template.py
│       │   │   ├── glific_webhook/      # Webhook processor
│       │   │   │   └── glific_webhook.py
│       │   │   └── tap_buddy_log/       # Audit log
│       │   │       └── tap_buddy_log.py
│       │   ├── services/                # Business logic modules
│       │   │   ├── glific_client.py     # Glific API wrapper
│       │   │   ├── lms_pipeline.py      # LMS data import
│       │   │   ├── lms_client.py        # LMS API client
│       │   │   ├── webhook_processor.py # Webhook handlers
│       │   │   ├── message_service.py   # Message sending
│       │   │   ├── constants.py         # Shared constants
│       │   │   └── logger.py            # Logging utility
│       │   ├── api.py                   # Public API endpoints
│       │   ├── hooks.py                 # Frappe hooks (lifecycle)
│       │   └── ui_test_tap_buddy.js     # Cypress test helpers
│       ├── requirements.txt             # Python dependencies
│       ├── pyproject.toml               # Package config
│       ├── pyrightconfig.json           # Type checking config
│       └── README.md                    # Original README
│
├── config/
│   ├── redis_cache.conf                # Cache server config
│   ├── redis_queue.conf                # Queue server config
│   ├── scheduler_process               # Job scheduler
│   └── pids/
│       └── redis_queue.rdb             # Queue persistence
│
├── sites/
│   ├── common_site_config.json         # Global site config
│   ├── apps.json                       # Installed apps list
│   ├── assets/                         # Built static assets
│   └── tapbuddy.local/                 # Site-specific files
│       ├── site_config.json            # Site configuration
│       ├── indexes/                    # DB indexes
│       ├── locks/                      # Frappe locks
│       └── public/private/logs/        # Site data
│
├── env/                                # Python venv
├── logs/                               # Application logs
├── Dockerfile                          # Docker setup
├── docker-compose.yml                  # Services orchestration
├── Procfile                            # Process management
├── script.py                           # Utility scripts
└── patches.txt                         # Migration patches
```

---

## Core Components (DocTypes)

A "DocType" in Frappe is a document schema + business logic unit. TAP Buddy has these:

### 1. **TAP Campaign** (tap_campaign.json)
**Purpose**: Central form for creating WhatsApp campaigns.

**Key Fields**:
- `campaign_name` (string): Human-readable name
- `school` (Link): School entity this campaign targets
- `template` (Link): WhatsApp template to use
- `message_template` (Text): Final message body (auto-populated from template)
- `status` (Select): "Draft", "Queued", "In Progress", "Completed"
- `scheduled_date` (Date): When to send

**Key Logic** (tap_campaign.py):
- `validate()`: Checks campaign_name is unique per school
- `before_submit()`: Sets status to "Queued"

**Client-Side Handler** (tap_campaign.js):
```javascript
frappe.ui.form.on("TAP Campaign", {
  template(frm) {
    // When template field changes, autofill message_template textarea
    // by fetching WhatsApp Template's message field
  }
})
```

### 2. **WhatsApp Template** (whatsapp_template.json)
**Purpose**: Stores WhatsApp message templates (reusable message blocks).

**Key Fields**:
- `message` (Text): The template message body (e.g., "Hello {{name}}, this is {{school}}")

**Usage**: Selected in TAP Campaign → autofills `message_template`.

### 3. **School** (school.json)
**Purpose**: Represents a school entity.

**Key Fields**:
- `school_name` (string): School identifier
- `principal_name` (string): Contact person

**Usage**: Linked in TAP Campaign to scope campaigns by school.

### 4. **TAP Buddy Settings** (tap_buddy_settings.json)
**Purpose**: Global configuration for the application.

**Key Fields**:
- `glific_api_key` (Password): Glific API authentication token
- `glific_organization_id` (string): Glific org ID
- `batch_size` (Int): How many messages to send per batch
- `rate_limit_per_second` (Int): Rate limiter for API calls
- `lms_api_url` (string): LMS endpoint
- `lms_api_key` (Password): LMS auth token

**Usage**: Service modules load this to configure external integrations.

### 5. **Glific Webhook** (glific_webhook.json)
**Purpose**: Receives and processes webhook events from Glific (message read, failed, bounced).

**Key Fields**:
- `webhook_id` (string): External webhook ID
- `payload` (JSON): Raw event data
- `status` (Select): "Pending", "Processed", "Failed"

**Logic**: `webhook_processor.py` parses incoming webhooks and updates campaign metrics.

### 6. **TAP Buddy Log** (tap_buddy_log.json)
**Purpose**: Audit trail of all campaign actions.

**Key Fields**:
- `campaign` (Link): Which campaign this log entry relates to
- `action` (string): Action type (e.g., "CAMPAIGN_CREATED", "MESSAGE_SENT")
- `details` (JSON): Structured log data
- `timestamp` (Datetime): When action occurred

---

## Service Modules (Business Logic)

Located in `/apps/tap_buddy/tap_buddy/services/`:

### **glific_client.py**
- **Purpose**: Wrapper around Glific WhatsApp API
- **Key Methods**:
  - `send_message(phone, text)` → sends SMS via Glific
  - `get_message_status(message_id)` → fetches delivery status
  - `get_organization_info()` → retrieves org details
- **Config Source**: Loads from TAP Buddy Settings DocType
- **Error Handling**: Catches `requests.RequestException`, logs to TAP Buddy Log

### **lms_pipeline.py**
- **Purpose**: Fetches student/teacher data from external LMS and imports into TAP Buddy
- **Key Functions**:
  - `run_lms_pipeline(limit, process_pending)` → Main ETL entry point
  - Returns: `{"status": "ok", "ingested": <count>}`
- **Data Flow**: LMS API → normalize → create School/Student records in Frappe
- **Scheduling**: Called via RQ background job from `hooks.py`

### **lms_client.py**
- **Purpose**: LMS API client (abstraction layer)
- **Key Methods**:
  - `get_students(school_id)` → fetch students from LMS
  - `get_classes(school_id)` → fetch class/grade structure
- **Config**: Uses `lms_api_url` and `lms_api_key` from TAP Buddy Settings

### **message_service.py**
- **Purpose**: High-level message sending orchestration
- **Key Methods**:
  - `send_campaign_messages(campaign_id)` → batch send all campaign messages
  - `throttle_and_send(phone_list, message)` → respects rate limits
- **Logic Flow**:
  1. Load campaign details + template
  2. Get target students from school
  3. For each student, render message with template variables
  4. Call `glific_client.send_message()`
  5. Log each send to TAP Buddy Log

### **webhook_processor.py**
- **Purpose**: Handles async Glific webhook events
- **Key Functions**:
  - `process_webhook(payload)` → parse Glific event and update campaign metrics
  - Triggered by Glific Webhook DocType `before_submit` hook
- **Event Types Handled**: `message.delivered`, `message.read`, `message.failed`

### **constants.py**
- **Purpose**: Centralized constant definitions
- **Key Constants**:
  - `STATUS_QUEUED = "Queued"`
  - `STATUS_IN_PROGRESS = "In Progress"`
  - `ACTION_TYPES = ["CAMPAIGN_CREATED", "MESSAGE_SENT", "WEBHOOK_RECEIVED"]`

### **logger.py**
- **Purpose**: Logging utility that writes to TAP Buddy Log
- **Key Methods**:
  - `log_action(campaign_id, action, details)` → creates TAP Buddy Log entry

---

## Testing

### Backend Tests
**Location**: Tests are auto-discovered in doctype folders (e.g., `tap_campaign/test_tap_campaign.py`)

**Run Command**:
```bash
cd /Users/blackstar/dev/client/tap-bench
bench --site tapbuddy.local run-tests --app tap_buddy
```

**Current Status**: ✅ All 16 tests PASS

**What's Tested**:
- DocType validation (campaign_name uniqueness, required fields)
- Controller logic (`before_submit`, `validate` hooks)
- Service layer functions (glific_client, lms_pipeline, message_service)
- API endpoints (if defined in api.py)

### UI Tests (Cypress)
**Location**: `/apps/frappe/cypress/integration/tap_buddy_ui_spec.js`

**Run Command**:
```bash
cd /Users/blackstar/dev/client/tap-bench/apps/frappe
npx cypress run --config-file cypress.config.js --config baseUrl=http://tapbuddy.local:8000 --spec cypress/integration/tap_buddy_ui_spec.js
```

**Current Test**: "creates campaign and auto-fills message template"
- **Steps**:
  1. Login via Cypress
  2. Create School (via API)
  3. Create WhatsApp Template (via API)
  4. Navigate to TAP Campaign form
  5. Fill campaign_name
  6. Select school
  7. Select template (should trigger autofill)
  8. Assert message_template contains "Hello"
  9. Save campaign
  10. Assert status = "Queued"

**Test Helpers**: `/apps/tap_buddy/tap_buddy/ui_test_tap_buddy.js` contains custom Cypress commands.

---

## Development Workflow

### 1. **Setup**
```bash
# Install Python dependencies
cd /Users/blackstar/dev/client/tap-bench
pip install -r apps/tap_buddy/requirements.txt

# Install Node dependencies (for Cypress)
cd apps/frappe
npm install

# Start Redis (if not running)
redis-server config/redis_cache.conf &
redis-server config/redis_queue.conf &

# Start Frappe dev server
bench --site tapbuddy.local serve
```

### 2. **Creating a New DocType**
```
bench make-doctype <app> <doctype-name>
```
This creates:
- `<doctype_name>.json` (schema)
- `<doctype_name>.py` (controller)
- `test_<doctype_name>.py` (test template)

### 3. **Modifying a DocType**
1. Edit `.json` file to add/remove fields (in web UI or via VS Code)
2. Edit `.py` file to add validation/business logic
3. Migrate database: `bench migrate`
4. Run tests: `bench run-tests`

### 4. **Adding Service Logic**
1. Create `.py` module in `services/`
2. Import it in controllers or API endpoints
3. Add tests alongside the module
4. Document public API in docstring

### 5. **Client-Side Scripting**
Form handlers use `frappe.ui.form.on("DocType Name", { ... })` pattern:
```javascript
frappe.ui.form.on("TAP Campaign", {
  refresh(frm) {
    // Runs every time form refreshes
  },
  template(frm) {
    // Runs when 'template' field changes
  },
  before_save(frm) {
    // Runs before form submit
    return frm.validate();
  }
})
```

### 6. **Running Tests**
- **Backend**: `bench run-tests --app tap_buddy`
- **Frontend**: `npx cypress run --spec <path>`
- **Both**: Run both in sequence

---

## Common Patterns & Conventions

### Form Validation
```python
# In DocType controller (e.g., tap_campaign.py)
def validate(self):
    if not self.campaign_name:
        frappe.throw("Campaign name required")
    
    # Check uniqueness
    existing = frappe.db.exists("TAP Campaign", {
        "campaign_name": self.campaign_name,
        "school": self.school
    })
    if existing:
        frappe.throw(f"Campaign '{self.campaign_name}' already exists for this school")
```

### Server-Side Field Updates
```python
# In controller
def before_submit(self):
    self.status = "Queued"  # Auto-set status before submission
```

### Client-Side Field Updates
```javascript
// In form handler
frappe.ui.form.on("TAP Campaign", {
  template(frm) {
    if (!frm.doc.template) return;
    
    frappe.db.get_value("WhatsApp Template", frm.doc.template, ["message"])
      .then(r => {
        frm.set_value("message_template", r.message.message);
        frm.refresh_field("message_template");
      });
  }
})
```

### API Endpoints
```python
# In api.py
@frappe.whitelist()
def send_campaign(campaign_id):
    """Send all messages in a campaign"""
    from tap_buddy.services.message_service import MessageService
    service = MessageService()
    result = service.send_campaign_messages(campaign_id)
    return result

# Call via: frappe.call({method: "tap_buddy.api.send_campaign", ...})
```

### Logging
```python
from tap_buddy.services.logger import log_action

log_action(
    campaign_id=campaign.name,
    action="MESSAGE_SENT",
    details={
        "phone": "+919876543210",
        "status": "success"
    }
)
```

---

## Configuration

### Site Config
**File**: `sites/tapbuddy.local/site_config.json`

```json
{
  "db_host": "localhost",
  "db_port": 5432,
  "db_name": "tapbuddy",
  "app_secret_key": "...",
  "admin_password": "...",
  "developer_mode": 1
}
```

### Frappe Hooks
**File**: `/apps/tap_buddy/tap_buddy/hooks.py`

Registers:
- **DocTypes**: List of all doctypes in the app
- **Fixtures**: Default data (e.g., initial Settings record)
- **Migrations**: Custom patch files
- **Scheduled Jobs**: RQ jobs (e.g., run_lms_pipeline every hour)
- **Webhooks**: Glific webhook listener routes

---

## Key Files Reference

| File | Purpose |
|------|---------|
| `tap_campaign.py` | Campaign form validation & lifecycle |
| `tap_campaign.js` | Client-side form autofill logic |
| `services/glific_client.py` | WhatsApp API communication |
| `services/message_service.py` | Campaign message orchestration |
| `services/lms_pipeline.py` | Student data import ETL |
| `services/webhook_processor.py` | Async event handling |
| `hooks.py` | Frappe lifecycle & scheduled jobs |
| `api.py` | Public API endpoints |
| `ui_test_tap_buddy.js` | Cypress test helpers |
| `tap_buddy_ui_spec.js` | Main Cypress test suite |

---

## Known Limitations & TODOs

1. **Environment Variables**: Currently hardcoded in service modules; should centralize in TAP Buddy Settings DocType
2. **Dry-Run Mode**: Message sending lacks a "preview" mode; all campaigns send immediately
3. **LMS Mapping**: Student phone numbers manually mapped; should add field mapping config
4. **Error Recovery**: No retry logic for failed Glific API calls; messages are lost
5. **Rate Limiting**: Hardcoded in constants; should be configurable per org

---

## Deployment Checklist

- [ ] All 16 backend tests pass
- [ ] All Cypress UI tests pass
- [ ] TAP Buddy Settings configured with Glific credentials
- [ ] LMS API endpoint tested and working
- [ ] Redis queue & cache servers running
- [ ] Database migrated to latest schema
- [ ] Static assets built (`bench build`)
- [ ] Gunicorn + Nginx configured for production

---

## Debugging Tips

### Form Not Loading
- Check browser console (F12) for JS errors
- Verify user has DocType permissions: `Settings > Users & Roles`
- Check site logs: `tail logs/tapbuddy.log`

### Message Not Sending
- Check TAP Buddy Log for action entries and errors
- Verify Glific credentials in TAP Buddy Settings
- Test Glific API directly: `curl -H "Authorization: Bearer <token>" https://api.glific.com/...`

### Tests Failing
- Run with verbose flag: `bench run-tests --app tap_buddy -v`
- Check test database is fresh: `bench migrate`
- Cypress: Open Cypress GUI to inspect steps: `npx cypress open`

---

## LLM Context Summary

This document provides a complete map of TAP Buddy's:
1. **What it does**: WhatsApp campaign management for schools
2. **How it's built**: Frappe framework with Python backend + JS frontend
3. **What exists**: 6 DocTypes, 7 service modules, comprehensive test suite
4. **How to modify**: DocType schema, controllers, service logic, form handlers
5. **How to test**: Backend test framework + Cypress UI tests
6. **How to deploy**: Environment config, Redis, migrations, Gunicorn

Use this README to onboard new developers or provide context to automated systems.
