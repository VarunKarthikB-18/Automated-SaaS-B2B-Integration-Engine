"""
B2B SaaS Integration Engine - FastAPI Entry Point
POST /api/v1/sync  →  clean → map → validate → persist
"""

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from pathlib import Path
from sqlalchemy.orm import Session
from typing import Any
import logging
import uuid
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent

from database import get_db, engine
from models import Base, CustomerRecord, SyncRequest, SyncResponse, SyncStatus
from cleaner import DataCleaner
from agent import ColumnMappingAgent

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("integration_engine")

# ── App bootstrap ──────────────────────────────────────────────────────────────
try:
    Base.metadata.create_all(bind=engine)
    logger.info("✔ Database tables verified / created")
except Exception as _db_err:
    logger.warning(
        "⚠ Could not connect to DB on startup (%s). "
        "Tables will be created on first request.",
        _db_err.__class__.__name__,
    )

app = FastAPI(
    title="B2B SaaS Integration Engine",
    description=(
        "Automated customer onboarding data pipeline: "
        "ingests messy JSON payloads, cleans, maps columns via LLM, "
        "validates with Pydantic, and persists to PostgreSQL / SQLite."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Singletons ─────────────────────────────────────────────────────────────────
cleaner = DataCleaner()
mapper  = ColumnMappingAgent()


# ── Structured error handlers ──────────────────────────────────────────────────
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"status": "error", "message": "Request validation failed", "detail": exc.errors()},
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"status": "error", "message": exc.detail},
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"status": "error", "message": "An internal server error occurred."},
    )


# ── Root – serve SyncEngine UI ────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_dashboard():
    template_path = BASE_DIR / "templates" / "index.html"
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


# ── Health ─────────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Infrastructure"])
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


# ── Main sync endpoint ─────────────────────────────────────────────────────────
@app.post(
    "/api/v1/sync",
    response_model=SyncResponse,
    tags=["Data Pipeline"],
    summary="Ingest and sync a customer record",
)
async def sync_customer(
    payload: SyncRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> SyncResponse:
    """
    Accepts a raw, messy customer JSON payload and runs it through the full
    integration pipeline:

    1. **Clean**    – normalise whitespace, format dates to ISO-8601, handle nulls
    2. **Map**      – use LLM agent to map arbitrary column names → canonical schema
    3. **Validate** – enforce strict Pydantic types
    4. **Persist**  – UPSERT validated record into database (insert or update on email conflict)

    Returns a sync receipt with a trace ID and the canonical record.
    """
    trace_id = str(uuid.uuid4())
    logger.info("▶ sync started | trace_id=%s | source=%s", trace_id, payload.source)

    # 1. Clean ──────────────────────────────────────────────────────────────────
    try:
        cleaned: dict[str, Any] = cleaner.clean(payload.data)
        logger.info("✔ cleaning complete | trace_id=%s", trace_id)
    except Exception as exc:
        logger.error("✖ cleaning failed | trace_id=%s | %s", trace_id, exc)
        raise HTTPException(status_code=422, detail=f"Data cleaning error: {exc}")

    # 2. Map columns ────────────────────────────────────────────────────────────
    try:
        mapped: dict[str, Any] = await mapper.map_columns(cleaned)
        logger.info("✔ column mapping complete | trace_id=%s | fields=%s", trace_id, list(mapped.keys()))
    except Exception as exc:
        logger.error("✖ column mapping failed | trace_id=%s | %s", trace_id, exc)
        raise HTTPException(status_code=422, detail=f"Column mapping error: {exc}")

    # 3. Validate ───────────────────────────────────────────────────────────────
    try:
        validated = CustomerRecord(**mapped)
    except Exception as exc:
        logger.error("✖ validation failed | trace_id=%s | %s", trace_id, exc)
        raise HTTPException(status_code=422, detail=f"Validation error: {exc}")

    # 4. Persist (UPSERT) ───────────────────────────────────────────────────────
    try:
        record, action = _upsert(db, validated, trace_id, payload.source)
        logger.info("✔ %s | trace_id=%s | record_id=%s", action, trace_id, record.id)
    except Exception as exc:
        logger.error("✖ DB write failed | trace_id=%s | %s", trace_id, exc)
        raise HTTPException(status_code=500, detail="Database persistence failed.")

    return SyncResponse(
        trace_id=trace_id,
        status=SyncStatus.success,
        record_id=str(record.id),
        canonical=validated.model_dump(),
    )


def _upsert(db: Session, record: CustomerRecord, trace_id: str, source: str):
    """
    UPSERT logic: insert a new CustomerORM row, or update the existing one if
    a record with the same email already exists.  Returns (orm_obj, action_label).
    """
    from models import CustomerORM  # local import avoids circular refs at module load

    fields = dict(
        trace_id=trace_id,
        source=source,
        first_name=record.first_name,
        last_name=record.last_name,
        phone_number=record.phone_number,
        company_name=record.company_name,
        plan_type=record.plan_type,
        signup_date=record.signup_date,
        country=record.country,
        mrr=record.mrr,
        is_active=record.is_active,
    )

    existing = db.query(CustomerORM).filter(CustomerORM.email == record.email).first()

    if existing:
        # UPDATE – apply every field from the new payload
        for attr, value in fields.items():
            setattr(existing, attr, value)
        db.commit()
        db.refresh(existing)
        return existing, "updated (upsert)"
    else:
        # INSERT – brand-new record
        orm_obj = CustomerORM(email=record.email, **fields)
        db.add(orm_obj)
        db.commit()
        db.refresh(orm_obj)
        return orm_obj, "inserted"
