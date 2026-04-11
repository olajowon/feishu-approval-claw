<p align="center">
  <img src="docs/logo.svg" width="80" height="80" alt="Logo">
</p>
<h1 align="center">Lark Approval Claw</h1>

<p align="center"><a href="README.md">中文</a></p>

> Real-time Lark approval event listener via WebSocket, automating the full pipeline: **Pre-check → Approval → Processing Group → @Openclaw Bot auto-handling (or low-code script processing)**.

---

## Core Design: Approval → Processing Group → Openclaw Bot

```
User submits approval in Lark
        ↓
Approval flow reaches "Pre-check" node
        ↓  Auto-execute pre-check script (Python)
        ↓  (True, ...)  → Node auto-approved
        ↓  (False, ...) → Node auto-rejected, reason written to Lark comment
        ↓
Approval finally approved
        ↓
Match processing script by "Subject"
        ├─ Script found → Execute script (Python, integrate with n8n / Dify workflows)
        └─ No script   → Auto-create Lark processing group
                            ├─ Add handlers (WORKER_USER_IDS)
                            ├─ Add Openclaw Bot (WORKER_BOT_APP_ID)
                            └─ Send structured @mention → Openclaw Bot triggers Skill
```

<!-- TODO: Replace with actual screenshot -->
![Processing Group @Openclaw Bot](docs/screenshots/openclaw-bot-group.png)

---

## Features

| Feature | Description |
|---------|-------------|
| **Pre-check Automation** | Auto-execute scripts at the "pre-check" node, approve or reject without manual intervention |
| **Processing Group** | Auto-create group, add members, @Openclaw Bot when no script matches |
| **Low-code Scripts** | Match and execute Python scripts by "Subject", integrate with n8n, Dify and other workflows in just a few lines |
| **Online Script Editor** | Syntax-highlighted editor + real-time debugging with parameters |
| **Environment Variables** | Configure KV pairs, auto-injected as `ENV` dict during script execution |
| **Audit Log** | All admin operations logged with username, IP, action details, and timestamp |
| **Hot Reload Config** | All settings can be modified in the admin panel, "Save & Restart" to apply |
| **Token Auto-refresh** | Periodic check of user access_token, auto-refresh when < 30 minutes remaining |

---

## Architecture

```
Lark Approval Platform
    ↓ WebSocket long connection (approval_instance P1 event, no public callback needed)
main.py ── Entry: initialize components, subscribe events, start WebSocket + HTTP
    │
    ├─ handlers/                     ── Approval event processing
    │   ├─ approval.py               ── Event router (dispatch pre-check / process)
    │   ├─ precheck.py               ── Pre-check node: run script → auto approve/reject
    │   └─ process.py                ── Approved: run script or create group + @Openclaw Bot
    │
    ├─ services/                     ── Core services
    │   ├─ db.py                     ── SQLite data layer (WAL mode, 7 tables)
    │   ├─ chat.py                   ── Lark IM (create group / add members / @Bot / dissolve)
    │   ├─ approval.py               ── Approval instance details + form parsing
    │   ├─ user_token.py             ── User OAuth token (persistent + auto-refresh + thread-safe)
    │   ├─ user_profile.py           ── User profile query (email/phone → open_id resolution)
    │   ├─ lark_client.py            ── Main app lark.Client singleton
    │   ├─ worker_bot.py             ── Openclaw Bot lark.Client singleton + bot open_id
    │   └─ notify.py                 ── Lark message sending (callable from scripts)
    │
    ├─ web/server.py                 ── Admin panel HTTP service (FastAPI + uvicorn)
    │   ├─ /admin routes (8 tabs)
    │   └─ /auth + /callback         ── Lark OAuth 2.0 authorization
    │
    ├─ scheduler/                    ── Background scheduled tasks
    │   ├─ Group TTL cleanup (hourly) ── Dissolve expired groups
    │   └─ Token patrol (every 10 min) ── Auto-refresh when access_token < 30 min remaining
    │
    └─ data/                         ── Data persistence (SQLite, Docker mount)
```

### Database Tables

| Table | Description |
|-------|-------------|
| `proc_tasks` | Processing task records (group status, script results) |
| `check_tasks` | Pre-check records (script results, approve/reject reasons) |
| `precheck_scripts` | Pre-check scripts (name, code, enabled) |
| `process_scripts` | Processing scripts (name, code, enabled) |
| `script_envvars` | Environment variables (key, desc, value, updated_at) |
| `settings` | System settings (key-value, overrides .env) |
| `admin_logs` | Admin audit log (username, ip, action, detail, created_at) |

---

## Admin Panel

> Access `http://localhost:9999/admin` (Basic Auth)

<!-- TODO: Replace with actual screenshots -->

**Processing Records**
![Processing Records](docs/screenshots/process-records.png)

**Custom Scripts**
![Custom Scripts](docs/screenshots/scripts.png)

**System Settings**
![System Settings](docs/screenshots/settings.png)

| Tab | Access | Description |
|-----|--------|-------------|
| Processing Records | All users | Processing history, script results, manual retry and group dissolution |
| Pre-check Records | All users | Pre-check execution history, approve/reject reasons, error details |
| Processing Scripts | All users | Create/edit processing scripts with syntax highlighting + live debugging |
| Pre-check Scripts | All users | Create/edit pre-check scripts, validate return format |
| Environment Variables | All users | Manage KV environment variables available to scripts |
| System Settings | Admin only | All configuration items, "Save & Restart" to apply |
| Audit Log | Admin only | Complete audit log of all admin operations |
| System Info | All users | Feature overview, architecture diagram, script writing guide |

---

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Minimal Configuration (.env)

```env
# Admin panel Basic Auth (read from .env only, not stored in database)
ADMIN_USER=admin
ADMIN_PASS=your_password

# Regular user accounts (optional, format: user1:pass1,user2:pass2)
# ACCOUNTS=ops:pass1,dev:pass2

# HTTP port (optional, default 9999)
HTTP_PORT=9999
```

All other settings can be configured in the admin panel under "System Settings".

### 3. Start

```bash
python main.py
```

Or with Docker:

```bash
cp .env.example .env
# Edit .env with your settings
docker compose up -d
```

- When core config (APP_ID / APP_SECRET) is missing, the system enters **admin-only mode**
- Access `http://localhost:9999/admin` to complete setup, "Save & Restart" to establish Lark WebSocket connection

### 4. Lark OAuth Authorization

Visit `http://localhost:9999/auth` to complete OAuth 2.0 authorization and obtain a **user-level token** (for sending messages, creating/dissolving groups). Takes effect immediately without restart.

---

## Lark App Configuration

> Uses **WebSocket long connection** for events — no callback URL needed. Enable "Long Connection for Events" in the Lark developer console.

### Required Permissions

| Permission | Purpose |
|------------|---------|
| `approval:approval` | Read approval definitions |
| `approval:approval:subscribe` | Subscribe to approval events |
| `im:message:send_as_bot` | Send group messages |
| `im:chat:create` | Create processing groups |
| `im:chat.group.member:add` | Add handlers and Bot to groups |
| `contact:user.base:readonly` | Read applicant information |

### Required Event Subscription

| Event | Format | Purpose |
|-------|--------|---------|
| Approval Task | P1 `approval_instance` | Real-time approval status changes, trigger pre-check and processing |

---

## Script Writing Guide

### Pre-check Script

**Trigger**: When the approval flow reaches a node matching the script name (`PRE_CHECK_NODE_NAME`, default "Pre-check").

```python
# ENV is auto-injected environment variable dict (configured in "Environment Variables" tab)
# api_key = ENV.get("MY_API_KEY", "")

def check(applicant: dict, form: dict) -> tuple[bool, str]:
    """
    applicant: {"name": "John", "open_id": "...", "email": "...", ...}
    form:      {"Subject": "...", "Reason": "...", ...}
    Return: (True, "") to approve  |  (False, "reason") to reject
    """
    if not form.get("Reason", "").strip():
        return False, "Reason cannot be empty"
    return True, ""
```

### Processing Script (Low-code)

**Trigger**: After approval, when "Subject" **exactly matches** the script name. Takes priority over default group creation. Integrate with n8n, Dify or any external workflow in just a few lines.

```python
import logging
from services.notify import send_feishu_message

logger = logging.getLogger(__name__)

# ENV is auto-injected environment variable dict (configured in "Environment Variables" tab)
# api_key = ENV.get("MY_API_KEY", "")

def run(applicant: dict, form: dict) -> str:
    """
    Return str to record in extra_info; raise exception to mark as error (retryable)
    """
    name    = applicant.get("name", "")
    open_id = applicant.get("open_id", "")
    send_feishu_message(
        receiver_ids=[open_id],
        receiver_id_type="open_id",
        title="Approved",
        content="Your request has been automatically processed.",
    )
    return f"Done, notified {name}"
```

**External Workflow Example** (n8n / Dify, just a few lines):

```python
import requests

def run(applicant: dict, form: dict) -> str:
    # Trigger n8n Webhook, push approval data to external workflow
    requests.post(ENV.get("N8N_WEBHOOK_URL"), json={
        "applicant": applicant["name"],
        "subject": form.get("Subject", ""),
        "form": form,
    }, timeout=30)
    return "n8n workflow triggered"
```

### Environment Variables (ENV)

KV pairs configured in the admin panel "**Environment Variables**" tab are auto-injected as the `ENV` dict during script execution. Ideal for storing API keys, credentials, and other sensitive parameters without hardcoding.

```python
# Use directly in scripts, no import needed
api_key  = ENV.get("MY_API_KEY", "")
base_url = ENV.get("API_BASE_URL", "https://example.com")
```

---

## Design Principles

- **Lightweight Deployment**: HTTP service based on FastAPI + uvicorn, SQLite database, no external middleware required
- **Three-tier Config Priority**: Database > `.env` > defaults, admin panel changes take highest priority
- **Zero-config Startup**: Missing core config still allows access to admin panel for online initialization
- **Script Isolation**: Each execution runs in an isolated `types.ModuleType` namespace, no cross-contamination
- **Create/Edit Separation**: API explicitly separates `/create` (with duplicate name detection) and `/edit` to prevent accidental overwrites
- **WebSocket Long Connection**: No public callback URL needed, works in private network deployments

---

## License

[MIT](LICENSE)
