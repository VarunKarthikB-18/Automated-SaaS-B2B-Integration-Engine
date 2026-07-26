# 🚀 B2B SaaS Integration Engine

> **Automated customer onboarding data pipeline** — ingests messy JSON payloads from any SaaS source, cleans them, maps arbitrary column names to a canonical schema via Google Gemini, validates with Pydantic v2, and persists to SQLite (local) or PostgreSQL / Supabase (production).

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![Gemini 2.0 Flash](https://img.shields.io/badge/Gemini-2.0%20Flash-4285F4?logo=google&logoColor=white)](https://aistudio.google.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red.svg)](https://www.sqlalchemy.org/)
[![Live on Render](https://img.shields.io/badge/Live%20Demo-Render-46E3B7?logo=render&logoColor=white)](https://b2b-saas-integration-engine.onrender.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🌐 Live Demo

> **API is live and publicly accessible on Render:**

| URL | Description |
|---|---|
| 🚀 [b2b-saas-integration-engine.onrender.com](https://b2b-saas-integration-engine.onrender.com/) | Root → auto-redirects to Swagger UI |
| 📄 [/docs](https://b2b-saas-integration-engine.onrender.com/docs) | Interactive Swagger UI — try endpoints in browser |
| 📘 [/redoc](https://b2b-saas-integration-engine.onrender.com/redoc) | ReDoc API reference |
| ❤️ [/health](https://b2b-saas-integration-engine.onrender.com/health) | Health check |
| 🔁 [/api/v1/sync](https://b2b-saas-integration-engine.onrender.com/docs#/Data%20Pipeline/sync_customer_api_v1_sync_post) | POST — sync a customer record |

---

## 📋 Table of Contents

- [What It Does](#what-it-does)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Quick Start — SQLite (Local)](#quick-start--sqlite-local)
- [Docker Compose — PostgreSQL](#docker-compose--postgresql)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Example Request / Response](#example-request--response)
- [Column Mapping Logic](#column-mapping-logic)
- [Data Cleaning Rules](#data-cleaning-rules)
- [Postman Collection](#postman-collection)

---

## What It Does

Every SaaS vendor ships data differently — inconsistent column names, messy dates, mixed null formats, random casing. This engine solves that at the API layer so your database always receives clean, canonical records.

**Send this in →**
```json
{
  "source": "hubspot",
  "data": {
    "fname": "  Alice  ",
    "cell_phone_v2": "+1 (555) 867-5309",
    "tier": "PRO",
    "signup_date": "26/07/2025",
    "mrr_usd": "$4,200",
    "active": "yes"
  }
}
```

**Get this out →**
```json
{
  "trace_id": "a3f2c1d4-...",
  "status": "success",
  "canonical": {
    "first_name": "Alice",
    "phone_number": "+1 (555) 867-5309",
    "plan_type": "pro",
    "signup_date": "2025-07-26",
    "mrr": 4200.0,
    "is_active": true
  }
}
```

---

## Architecture

```
POST /api/v1/sync
        │
        ▼
┌─────────────────────┐
│  1. DataCleaner     │  cleaner.py
│  • Normalise keys   │  → strip whitespace, lowercase, underscores
│  • Parse dates      │  → any format → ISO-8601 (YYYY-MM-DD)
│  • Detect nulls     │  → 15 sentinel patterns → None
│  • Coerce types     │  → booleans, currency floats
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  2. ColumnMapping   │  agent.py
│     Agent           │
│  ① Exact match      │  → already canonical? keep it
│  ② 40 alias rules   │  → cell_phone_v2 → phone_number
│  ③ Gemini 2.0 Flash │  → LLM inference for unknown columns
│  ④ Fuzzy fallback   │  → token overlap scoring (no API key)
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  3. Pydantic v2     │  models.py
│     Validation      │
│  • 10 typed fields  │
│  • 4 field validators│
│  • EmailStr check   │
│  • mrr ≥ 0 enforced │
└────────┬────────────┘
         │
         ▼
┌─────────────────────┐
│  4. DB Persist      │  database.py
│  SQLite  (local)    │  ← default, zero install
│  PostgreSQL (prod)  │  ← Supabase / Render
│  SQLAlchemy ORM     │
└─────────────────────┘
         │
         ▼
  SyncResponse JSON
  { trace_id, record_id, canonical }
```

---

## Project Structure

```
b2b-saas-integration-engine/
│
├── main.py                  # FastAPI app · 3 endpoints · 4-stage pipeline
├── cleaner.py               # Data cleaning module (dates, nulls, whitespace)
├── agent.py                 # Gemini LLM column mapping agent + fallbacks
├── models.py                # Pydantic v2 schemas · SQLAlchemy ORM
├── database.py              # SQLite (dev) / PostgreSQL (prod) engine setup
│
├── requirements.txt         # 10 Python dependencies
├── Dockerfile               # Python 3.12-slim · 5-step layered build
├── docker-compose.yml       # FastAPI + PostgreSQL 16 stack
│
├── .env.example             # Environment variable template
├── .gitignore               # Excludes .env, *.db, __pycache__
├── postman_collection.json  # 6 ready-to-use API test requests
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **API Framework** | FastAPI 0.111+ with Uvicorn ASGI server |
| **LLM / AI** | Google Gemini 2.0 Flash (`google-generativeai`) |
| **Validation** | Pydantic v2 with `EmailStr`, regex, custom validators |
| **ORM** | SQLAlchemy 2.0 with DeclarativeBase |
| **Database (local)** | SQLite — `sqlite:///./test.db` — zero install |
| **Database (prod)** | PostgreSQL / Supabase via `psycopg2-binary` |
| **Containerisation** | Docker + Docker Compose |
| **Deployment** | Render (live) |
| **Date parsing** | `python-dateutil` — handles any date format |

---

## Quick Start — SQLite (Local)

No Docker. No PostgreSQL. No setup. Just Python.

```bash
# 1. Clone the repo
git clone https://github.com/VarunKarthikB-18/Automated-SaaS-B2B-Integration-Engine.git
cd Automated-SaaS-B2B-Integration-Engine

# 2. (Recommended) create a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
python -m uvicorn main:app --reload
```

✅ Server runs at **`http://127.0.0.1:8000`**
✅ SQLite database (`test.db`) and all tables created automatically
✅ Visit `http://localhost:8000` → auto-redirects to Swagger UI

---

## Docker Compose — PostgreSQL

### Prerequisites
- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

```bash
# 1. Configure environment
cp .env.example .env
# Edit .env — add GEMINI_API_KEY for LLM column mapping

# 2. Start the full stack (FastAPI + PostgreSQL 16)
docker compose up --build

# Run in background
docker compose up --build -d

# View logs
docker compose logs -f api

# Tear down
docker compose down

# Fresh start (wipe DB volume)
docker compose down -v
```

| Container | Port | Description |
|---|---|---|
| `b2b_api` | `8000` | FastAPI + Uvicorn |
| `b2b_postgres` | `5432` | PostgreSQL 16 Alpine |

---

## Environment Variables

Copy `.env.example` → `.env` and configure:

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | *(unset)* | Full DB URL — overrides all POSTGRES_* vars |
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_DB` | `b2b_integration` | Database name |
| `POSTGRES_USER` | `b2b_user` | Database user |
| `POSTGRES_PASSWORD` | `b2b_password` | Database password |
| `GEMINI_API_KEY` | *(unset)* | Google Gemini key — get free at [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini model to use |
| `SQL_ECHO` | `false` | Set `true` to log all SQL to console |
| `LOG_LEVEL` | `info` | Uvicorn log level |

**Database selection priority (no `.env` needed locally):**
```
DATABASE_URL  →  POSTGRES_* vars  →  sqlite:///./test.db  ✅ (auto-default)
```

---

## API Endpoints

### `GET /`
Redirects to `/docs`. Hidden from the OpenAPI schema.

---

### `GET /health`
Liveness check — returns `200 OK` when the server is up.

```json
{ "status": "ok", "timestamp": "2025-07-27T00:00:00.000000" }
```

---

### `POST /api/v1/sync`

The core integration endpoint. Accepts any raw JSON payload and runs the full 4-stage pipeline.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | `string` | No | Origin system (e.g. `hubspot`, `salesforce`) |
| `data` | `object` | **Yes** | Raw customer payload — any column names accepted |

**Response `200 OK`:**

| Field | Type | Description |
|---|---|---|
| `trace_id` | `string` | UUID for this sync transaction |
| `status` | `string` | `success` / `partial` / `failed` |
| `record_id` | `string` | UUID of the inserted DB record |
| `canonical` | `object` | Validated canonical record that was persisted |
| `synced_at` | `datetime` | UTC timestamp |

**Error responses:**

| Code | When |
|---|---|
| `422` | Cleaning / mapping / Pydantic validation failed |
| `500` | Database write error |

---

## Example Request / Response

### Input — messy HubSpot payload

```json
POST /api/v1/sync
{
  "source": "hubspot",
  "data": {
    "fname":          "  Alice  ",
    "lname":          "Smith",
    "email_address":  "alice@acme.com",
    "cell_phone_v2":  "+1 (555) 867-5309",
    "company":        "  Acme   Corp  ",
    "tier":           "PRO",
    "signup_date":    "26/07/2025",
    "mrr_usd":        "$4,200",
    "active":         "yes",
    "country_code":   "us"
  }
}
```

### Output — clean canonical record

```json
{
  "trace_id":  "a3f2c1d4-7b8e-4f2a-9c0d-1e2f3a4b5c6d",
  "status":    "success",
  "record_id": "e5d4c3b2-a1f0-4e3d-8c7b-6a5f4e3d2c1b",
  "canonical": {
    "first_name":   "Alice",
    "last_name":    "Smith",
    "email":        "alice@acme.com",
    "phone_number": "+1 (555) 867-5309",
    "company_name": "Acme Corp",
    "plan_type":    "pro",
    "signup_date":  "2025-07-26",
    "mrr":          4200.0,
    "is_active":    true,
    "country":      "US"
  },
  "synced_at": "2025-07-26T13:00:00.000000"
}
```

---

## Column Mapping Logic

`ColumnMappingAgent` resolves incoming field names through **4 cascading strategies**:

```
1. Exact canonical match   → key already in schema? use it directly
2. 40 hard-coded aliases   → cell_phone_v2 → phone_number, mrr_usd → mrr ...
3. Gemini 2.0 Flash (LLM)  → AI predicts best canonical match from schema
4. Fuzzy token overlap     → last resort when no API key is configured
```

**10 canonical target columns:**

| Column | Description |
|---|---|
| `first_name` | Given / first name |
| `last_name` | Family / last name |
| `email` | Primary email (required) |
| `phone_number` | Primary phone — any format |
| `company_name` | Legal company name |
| `plan_type` | Subscription tier |
| `signup_date` | ISO-8601 signup date (YYYY-MM-DD) |
| `country` | Country name or ISO 3166-1 alpha-2 code |
| `mrr` | Monthly recurring revenue in USD |
| `is_active` | Boolean account status |

---

## Data Cleaning Rules

`DataCleaner` transforms every value before mapping:

| Type | Rule |
|---|---|
| **Keys** | Lowercase · strip whitespace · spaces/dashes/dots → `_` · collapse `__` |
| **Null sentinels** | `""`, `"null"`, `"NULL"`, `"N/A"`, `"none"`, `"undefined"`, `"-"` → `None` (15 patterns) |
| **Strings** | Strip edges · collapse internal whitespace |
| **Dates** | Any recognisable format → `YYYY-MM-DD` via `python-dateutil` |
| **Booleans** | `"yes"/"true"/"1"/"on"` → `True` · `"no"/"false"/"0"/"off"` → `False` |
| **Numbers** | Strip `$`, commas, currency symbols → `float` |
| **Nested dicts** | Cleaned recursively |
| **Lists** | Each element cleaned individually |

---

## Postman Collection

Import [`postman_collection.json`](./postman_collection.json) into Postman to get 6 pre-built requests:

| Request | Purpose |
|---|---|
| `GET /health` | Liveness check |
| `POST /sync` — HubSpot payload | Real-world messy data with alias columns |
| `POST /sync` — Salesforce payload | PascalCase + `__c` custom fields |
| `POST /sync` — Minimal (email only) | Minimum valid payload |
| `POST /sync` — Null sentinels | Tests `"N/A"`, `"NULL"`, `"undefined"` cleaning |
| `POST /sync` — Missing email | Expects `422` validation error |

**Import:** Postman → **Import** → select `postman_collection.json` → done.
The `{{baseUrl}}` variable defaults to `http://localhost:8000`.

---

## License

MIT © 2025 B2B SaaS Integration Engine
