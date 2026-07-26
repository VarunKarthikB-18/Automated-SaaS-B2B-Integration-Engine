"""
database.py – SQLAlchemy database connection setup
---------------------------------------------------
Local development  →  SQLite  (sqlite:///./test.db)   ← default, zero-install
Production / CI    →  PostgreSQL via DATABASE_URL or POSTGRES_* env vars

Exposes:
  • engine        – SQLAlchemy engine instance
  • SessionLocal  – session factory
  • get_db()      – FastAPI dependency that yields a scoped DB session
"""

import os
import logging
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool

logger = logging.getLogger("integration_engine.database")


# ── Connection URL builder ──────────────────────────────────────────────────────
def _build_database_url() -> str:
    """
    Determine the database URL using the following priority order:

    1. ``DATABASE_URL`` env var   – full connection string (Heroku / Railway style)
    2. ``POSTGRES_*`` env vars    – assembled into a psycopg2 URL
    3. Default                    – SQLite local file  ``sqlite:///./test.db``
    """
    # 1. Explicit full URL
    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        # Normalize Heroku-style postgres:// → postgresql://
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        logger.info("Using DATABASE_URL from environment")
        return db_url

    # 2. Individual Postgres vars
    pg_vars = ["POSTGRES_HOST", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"]
    if any(os.getenv(v) for v in pg_vars):
        host     = os.getenv("POSTGRES_HOST",     "localhost")
        port     = os.getenv("POSTGRES_PORT",     "5432")
        user     = os.getenv("POSTGRES_USER",     "b2b_user")
        password = os.getenv("POSTGRES_PASSWORD", "b2b_password")
        db_name  = os.getenv("POSTGRES_DB",       "b2b_integration")
        url = f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{db_name}"
        logger.info("Using PostgreSQL: %s:%s/%s", host, port, db_name)
        return url

    # 3. SQLite default – no Docker, no Postgres needed
    sqlite_url = "sqlite:///./test.db"
    logger.info("No database env vars set – defaulting to local SQLite: %s", sqlite_url)
    return sqlite_url


# ── Resolve URL at import time ─────────────────────────────────────────────────
DATABASE_URL: str = _build_database_url()
_is_sqlite: bool  = DATABASE_URL.startswith("sqlite")


# ── Engine ─────────────────────────────────────────────────────────────────────
if _is_sqlite:
    # SQLite requires check_same_thread=False for use with FastAPI's async workers
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,          # single shared connection – safe for SQLite
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )
else:
    # PostgreSQL – connection pool tuned for concurrent workloads
    engine = create_engine(
        DATABASE_URL,
        poolclass=QueuePool,
        pool_size=10,        # persistent connections kept alive
        max_overflow=20,     # burst connections allowed under load
        pool_pre_ping=True,  # discard stale connections before use
        pool_recycle=1800,   # recycle every 30 minutes to avoid timeouts
        echo=os.getenv("SQL_ECHO", "false").lower() == "true",
    )

logger.info(
    "Engine ready | backend=%s",
    "SQLite" if _is_sqlite else DATABASE_URL.split("@")[-1],   # hide credentials
)


# ── Session factory ────────────────────────────────────────────────────────────
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,   # keep ORM objects usable after commit
)


# ── FastAPI dependency ─────────────────────────────────────────────────────────
def get_db() -> Generator[Session, None, None]:
    """
    Yields a database session tied to a single request lifecycle.
    Rolls back automatically on error; always closes on exit.

    Usage::

        from database import get_db
        from sqlalchemy.orm import Session

        @app.post("/example")
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Health-check helper ────────────────────────────────────────────────────────
def check_db_connection() -> bool:
    """
    Runs a lightweight ``SELECT 1`` to verify the database is reachable.
    Returns ``True`` on success, ``False`` otherwise (logs the error).
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as exc:
        logger.error("Database health check failed: %s", exc)
        return False
