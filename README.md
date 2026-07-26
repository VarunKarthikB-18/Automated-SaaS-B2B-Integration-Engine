# 🚀 B2B SaaS Integration Engine

> **Automated customer onboarding data pipeline** — ingests messy JSON payloads, cleans them, maps arbitrary column names to a canonical schema via an LLM agent, validates with Pydantic, and persists to SQLite (dev) or PostgreSQL (production).

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111%2B-009688.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0%2B-red.svg)](https://www.sqlalchemy.org/)
[![Live on Render](https://img.shields.io/badge/Live%20Demo-Render-46E3B7?logo=render&logoColor=white)](https://b2b-saas-integration-engine.onrender.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 🌐 Live Demo

> **API is live and publicly accessible:**
>
> | URL | Description |
> |---|---|
> | 🚀 [b2b-saas-integration-engine.onrender.com](https://b2b-saas-integration-engine.onrender.com/) | Root → redirects to Swagger UI |
> | 📄 [/docs](https://b2b-saas-integration-engine.onrender.com/docs) | Interactive Swagger UI |
> | 📘 [/redoc](https://b2b-saas-integration-engine.onrender.com/redoc) | ReDoc API reference |
> | ❤️ [/health](https://b2b-saas-integration-engine.onrender.com/health) | Health check |
> | 🔁 [/api/v1/sync](https://b2b-saas-integration-engine.onrender.com/docs#/Data%20Pipeline/sync_customer_api_v1_sync_post) | POST – sync a customer record |

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Quick Start — SQLite (Local Dev)](#quick-start--sqlite-local-dev)
- [Setup — Docker Compose (PostgreSQL)](#setup--docker-compose-postgresql)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [Example Request / Response](#example-request--response)
- [Column Mapping Logic](#column-mapping-logic)
- [Data Cleaning Rules](#data-cleaning-rules)
- [Postman Collection](#postman-collection)
- [Roadmap](#roadmap)

---

## Overview

Enterprises integrating multiple SaaS products face a common problem: every vendor ships data in a different shape — inconsistent column names, messy dates, mixed null formats, and arbitrary casing. This engine solves that at the API layer, so your database always receives clean, canonical records.

**Core capabilities:**

| Capability | Detail |
|---|---|
| 🧹 Data Cleaning | Whitespace normalisation, ISO-8601 date parsing, null-sentinel detection, boolean + numeric coercion |
| 🤖 LLM Column Mapping | GPT-4o-mini maps unknown field names → canonical schema (e.g. `cell_phone_v2` → `phone_number`) |
| 🔁 Rule-based Fallback | 40+ hard-coded aliases + fuzzy token overlap when OpenAI key is absent |
| ✅ Pydantic Validation | Strict type enforcement before any DB write |
| 🗄️ Dual DB Support | SQLite (zero-install, local) or PostgreSQL (production) — auto-detected from env vars |
| 🐳 Docker Compose | One-command stack: FastAPI + PostgreSQL 16 |
| 📄 Auto Docs | Swagger UI at `/docs`, ReDoc at `/redoc` |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                     POST /api/v1/sync                                │
│              (raw customer JSON from any SaaS source)                │
└────────────────────────────┬─────────────────────────────────────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │   1. DataCleaner         │  cleaner.py
              │  ─────────────────────   │
              │  • Normalise key names   │
              │  • Strip whitespace      │
              │  • Parse dates → ISO8601 │
              │  • Coerce nulls/bools/   │
              │    numbers               │
              └──────────────┬───────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │  2. ColumnMappingAgent   │  agent.py
              │  ─────────────────────   │
              │  ① Exact canonical match │
              │  ② Hard-coded alias map  │
              │  ③ LLM (GPT-4o-mini)     │
              │  ④ Fuzzy token overlap   │
              └──────────────┬───────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │  3. Pydantic Validation  │  models.py
              │  ─────────────────────   │
              │  CustomerRecord schema   │
              │  EmailStr, phone regex,  │
              │  mrr ≥ 0, date pattern   │
              └──────────────┬───────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │  4. Database Persist     │  database.py
              │  ─────────────────────   │
              │  SQLite  (local dev)     │
              │  PostgreSQL (production) │
              │  SQLAlchemy ORM insert   │
              └──────────────┬───────────┘
                             │
                             ▼
              ┌──────────────────────────┐
              │   SyncResponse JSON      │
              │  trace_id, record_id,    │
              │  canonical record        │
              └──────────────────────────┘
```

---

## Project Structure

```
b2b-saas-integration-engine/
│
├── main.py              # FastAPI app · /api/v1/sync endpoint
├── cleaner.py           # Data transformation module
├── agent.py             # LLM column mapping agent
├── models.py            # Pydantic schemas + SQLAlchemy ORM
├── database.py          # DB engine, session factory, get_db()
│
├── requirements.txt     # Python dependencies
├── Dockerfile           # Python 3.12-slim image
├── docker-compose.yml   # FastAPI + PostgreSQL stack
│
├── .env.example         # Environment variable template
├── .gitignore
├── postman_collection.json  # Postman API test collection
└── README.md
```

---

## Quick Start — SQLite (Local Dev)

No Docker, no PostgreSQL needed. The engine auto-creates `test.db` in the project directory.

### Prerequisites

- Python 3.11 or higher
- `pip`

### Steps

```bash
# 1. Clone / enter project directory
cd b2b-saas-integration-engine

# 2. (Optional) create a virtual environment
python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
python -m uvicorn main:app --reload
```

The server starts at **`http://127.0.0.1:8000`**.  
SQLite database (`test.db`) and all tables are created automatically.

| URL | Purpose |
|---|---|
| `http://localhost:8000/docs` | Swagger UI (interactive) |
| `http://localhost:8000/redoc` | ReDoc documentation |
| `http://localhost:8000/health` | Health check |

---

## Setup — Docker Compose (PostgreSQL)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/)

### Steps

```bash
# 1. Copy and configure environment file
cp .env.example .env
# Edit .env → add OPENAI_API_KEY if you want LLM column mapping

# 2. Start the full stack (API + PostgreSQL)
docker compose up --build

# To run in background (detached)
docker compose up --build -d

# 3. View logs
docker compose logs -f api

# 4. Stop everything
docker compose down

# Stop and delete database volume (fresh start)
docker compose down -v
```

**Services:**

| Service | Container | Port |
|---|---|---|
| FastAPI API | `b2b_api` | `8000` |
| PostgreSQL 16 | `b2b_postgres` | `5432` |

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
| `OPENAI_API_KEY` | *(unset)* | GPT-4o-mini key for LLM mapping (optional) |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI model to use |
| `SQL_ECHO` | `false` | Set `true` to log raw SQL to console |
| `LOG_LEVEL` | `info` | Uvicorn log level |

**DB selection priority (no `.env` needed for local SQLite):**
```
DATABASE_URL  →  POSTGRES_* vars  →  sqlite:///./test.db  (default)
```

---

## API Endpoints

### `GET /health`

Lightweight liveness check.

**Response `200 OK`:**
```json
{
  "status": "ok",
  "timestamp": "2025-07-26T13:00:00.000000"
}
```

---

### `POST /api/v1/sync`

**The core integration endpoint.** Accepts a raw customer JSON payload, runs it through the full 4-step pipeline, and returns a sync receipt.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | `string` | No | Origin system identifier (e.g. `hubspot`, `salesforce`) |
| `data` | `object` | **Yes** | Raw customer payload — any column names accepted |

**Response `200 OK`:**

| Field | Type | Description |
|---|---|---|
| `trace_id` | `string` | UUID for this sync transaction (use for debugging) |
| `status` | `string` | `success` / `partial` / `failed` |
| `record_id` | `string` | UUID of the inserted DB record |
| `canonical` | `object` | The validated, canonical customer record |
| `synced_at` | `datetime` | UTC timestamp of the sync |

**Error responses:**

| Code | Meaning |
|---|---|
| `422` | Cleaning, column mapping, or Pydantic validation failed |
| `500` | Database write error |

---

### `GET /docs`

Auto-generated **Swagger UI** — try all endpoints interactively in the browser.

### `GET /redoc`

Auto-generated **ReDoc** API reference.

---

## Example Request / Response

### Messy input (as received from HubSpot)

```json
POST /api/v1/sync
Content-Type: application/json

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

### Canonical output

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

### What the pipeline did

| Step | Input | Output |
|---|---|---|
| Clean keys | `fname`, `cell_phone_v2`, `mrr_usd` | `fname`, `cell_phone_v2`, `mrr_usd` (lowercased) |
| Clean values | `"  Alice  "`, `"26/07/2025"`, `"$4,200"`, `"yes"` | `"Alice"`, `"2025-07-26"`, `4200.0`, `true` |
| Map columns | `fname` → `first_name`, `cell_phone_v2` → `phone_number`, `tier` → `plan_type` | Canonical keys |
| Validate | All fields through `CustomerRecord` Pydantic model | Passes ✅ |
| Persist | INSERT into `customer_records` | `record_id` returned |

---

## Column Mapping Logic

The `ColumnMappingAgent` maps incoming column names to the canonical schema in four stages:

```
1. Exact match      → already a canonical column name? Use it directly.
2. Alias rules      → 40+ hard-coded mappings (cell_phone → phone_number, etc.)
3. LLM (GPT-4o)     → ask OpenAI to predict the best canonical match
4. Fuzzy fallback   → token overlap scoring when LLM is unavailable
```

**Canonical schema columns:**

| Column | Description |
|---|---|
| `first_name` | Given / first name |
| `last_name` | Family / last name |
| `email` | Primary email address |
| `phone_number` | Primary phone (any format) |
| `company_name` | Legal company name |
| `plan_type` | Subscription tier (free / starter / pro / enterprise) |
| `signup_date` | ISO-8601 signup date (YYYY-MM-DD) |
| `country` | Country name or ISO 3166-1 alpha-2 code |
| `mrr` | Monthly recurring revenue in USD |
| `is_active` | Boolean account status |

---

## Data Cleaning Rules

`DataCleaner` applies the following transformations:

| Type | Rule |
|---|---|
| **Keys** | Lowercase, strip whitespace, spaces/dashes/dots → `_`, collapse `__` |
| **Null values** | `""`, `"null"`, `"N/A"`, `"none"`, `"undefined"`, `"-"` → Python `None` |
| **Strings** | Strip leading/trailing whitespace, collapse internal whitespace runs |
| **Dates** | Any recognisable format → `YYYY-MM-DD` via `python-dateutil` |
| **Booleans** | `"yes"/"true"/"1"/"on"` → `True` · `"no"/"false"/"0"/"off"` → `False` |
| **Numbers** | Strip `$`, commas, currency symbols → `float` |
| **Nested dicts** | Cleaned recursively |
| **Lists** | Each element cleaned individually |

---

## Postman Collection

A ready-to-use Postman collection is included at [`postman_collection.json`](./postman_collection.json).

**To import:**
1. Open Postman → **Import** → **File**
2. Select `postman_collection.json`
3. The collection **B2B SaaS Integration Engine** will appear with all requests pre-configured

**Included requests:**
- `GET  /health` — liveness check
- `POST /api/v1/sync` — HubSpot-style messy payload
- `POST /api/v1/sync` — Salesforce-style payload
- `POST /api/v1/sync` — Minimal payload (email only)
- `POST /api/v1/sync` — Invalid payload (missing email → expect 422)

---

## Roadmap

- [ ] Async database writes with SQLAlchemy async session
- [ ] Batch sync endpoint (`POST /api/v1/sync/batch`)
- [ ] Webhook support for real-time SaaS push events
- [ ] Alembic migrations for schema versioning
- [ ] Prometheus metrics endpoint
- [ ] Rate limiting middleware
- [ ] JWT authentication

---

## License

MIT © 2025 B2B SaaS Integration Engine
