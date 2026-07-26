"""
models.py – Pydantic v2 validation schemas + SQLAlchemy ORM
All incoming data must pass these validators before any DB write.
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase


# ══════════════════════════════════════════════════════════════════════════════
# SQLAlchemy Base & ORM model
# ══════════════════════════════════════════════════════════════════════════════

class Base(DeclarativeBase):
    pass


class CustomerORM(Base):
    """PostgreSQL table: customer_records"""

    __tablename__ = "customer_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trace_id = Column(String(36), nullable=False, index=True)
    source = Column(String(120), nullable=True)

    # Core customer fields
    first_name = Column(String(120), nullable=True)
    last_name = Column(String(120), nullable=True)
    email = Column(String(254), nullable=False, index=True, unique=True)
    phone_number = Column(String(30), nullable=True)
    company_name = Column(String(255), nullable=True)
    plan_type = Column(String(60), nullable=True)
    signup_date = Column(String(10), nullable=True)   # stored as ISO-8601 string
    country = Column(String(100), nullable=True)
    mrr = Column(Float, nullable=True)
    is_active = Column(Boolean, nullable=True)

    # Audit timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ══════════════════════════════════════════════════════════════════════════════
# Pydantic enums
# ══════════════════════════════════════════════════════════════════════════════

class PlanType(str, Enum):
    free = "free"
    starter = "starter"
    pro = "pro"
    enterprise = "enterprise"
    custom = "custom"


class SyncStatus(str, Enum):
    success = "success"
    partial = "partial"
    failed = "failed"


# ══════════════════════════════════════════════════════════════════════════════
# Core validated customer record (Pydantic)
# ══════════════════════════════════════════════════════════════════════════════

class CustomerRecord(BaseModel):
    """
    Canonical, fully-validated customer record.
    Must be constructed after cleaning + column mapping.
    """

    model_config = {"str_strip_whitespace": True, "use_enum_values": True}

    # Required
    email: EmailStr = Field(..., description="Primary email address")

    # Optional strings
    first_name: Optional[str] = Field(None, max_length=120)
    last_name: Optional[str] = Field(None, max_length=120)
    phone_number: Optional[str] = Field(None, max_length=30)
    company_name: Optional[str] = Field(None, max_length=255)
    country: Optional[str] = Field(None, max_length=100)

    # Plan
    plan_type: Optional[str] = Field(None, max_length=60)

    # Date stored as string in ISO-8601
    signup_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    # Revenue
    mrr: Optional[float] = Field(None, ge=0, description="Monthly recurring revenue (USD)")

    # Status
    is_active: Optional[bool] = None

    # ── field validators ───────────────────────────────────────────────────────
    @field_validator("phone_number", mode="before")
    @classmethod
    def validate_phone(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        cleaned = re.sub(r"[^\d\+\-\(\)\s]", "", str(v)).strip()
        if len(cleaned) < 7:
            return None
        return cleaned

    @field_validator("plan_type", mode="before")
    @classmethod
    def normalise_plan(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v).lower().strip()

    @field_validator("mrr", mode="before")
    @classmethod
    def coerce_mrr(cls, v: Any) -> Optional[float]:
        if v is None:
            return None
        try:
            return float(str(v).replace(",", "").replace("$", "").strip())
        except (ValueError, TypeError):
            return None

    @field_validator("country", mode="before")
    @classmethod
    def normalise_country(cls, v: Any) -> Optional[str]:
        if v is None:
            return None
        return str(v).strip().upper() if len(str(v).strip()) == 2 else str(v).strip().title()

    @model_validator(mode="before")
    @classmethod
    def require_email(cls, values: Any) -> Any:
        if isinstance(values, dict) and not values.get("email"):
            raise ValueError("email is required and cannot be empty")
        return values


# ══════════════════════════════════════════════════════════════════════════════
# Request / Response schemas
# ══════════════════════════════════════════════════════════════════════════════

class SyncRequest(BaseModel):
    """
    The body accepted by POST /api/v1/sync.
    `data` is intentionally an open dict – it can contain any column names.
    """

    source: str = Field(
        default="unknown",
        max_length=120,
        description="Identifier for the origin system (e.g. salesforce, hubspot)",
    )
    data: dict[str, Any] = Field(
        ...,
        description="Raw customer payload from the source system",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "source": "hubspot",
                "data": {
                    "fname": "  Alice  ",
                    "lname": "Smith",
                    "email_address": "alice@example.com",
                    "cell_phone_v2": "+1 (555) 867-5309",
                    "company": "Acme Corp",
                    "tier": "pro",
                    "signup_date": "26/07/2025",
                    "mrr_usd": "$4,200",
                    "active": "yes",
                    "country_code": "us",
                },
            }
        }
    }


class SyncResponse(BaseModel):
    """Returned by POST /api/v1/sync on success."""

    trace_id: str = Field(..., description="Unique ID for this sync transaction")
    status: SyncStatus
    record_id: str = Field(..., description="Database UUID of the newly inserted record")
    canonical: dict[str, Any] = Field(
        ..., description="The validated canonical record that was persisted"
    )
    synced_at: datetime = Field(default_factory=datetime.utcnow)
