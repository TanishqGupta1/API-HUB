from typing import Any, Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


# ── Push request envelope ──

class PushTarget(BaseModel):
    system: str = "ops"
    customer_id: UUID


class PushSource(BaseModel):
    supplier_slug: str


class PushProductRef(BaseModel):
    supplier_sku: str


class PushCallback(BaseModel):
    url: str
    secret: Optional[str] = None


class PushRequest(BaseModel):
    target: PushTarget
    source: PushSource
    product_ref: PushProductRef
    product: Optional[dict[str, Any]] = None   # inline upsert (future)
    decorations: list[dict[str, Any]] = []
    dry_run: bool = False
    callback: Optional[PushCallback] = None


# ── Push responses ──

class PushRequestLinks(BaseModel):
    self: str


class PushRequestAccepted(BaseModel):
    push_log_id: UUID
    status: str
    customer_id: UUID
    supplier_slug: str
    supplier_sku: str
    ops_product_id: Optional[str] = None
    dry_run: bool = False
    callback_status: str = "not_requested"
    created_at: datetime
    links: PushRequestLinks


class StepResultOut(BaseModel):
    step: str
    ok: bool
    ops_id: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[int] = None


class PushStatusOut(BaseModel):
    push_log_id: UUID
    status: str
    customer_id: UUID
    supplier_slug: Optional[str] = None
    supplier_sku: Optional[str] = None
    ops_product_id: Optional[str] = None
    error: Optional[str] = None
    step_results: Optional[list[StepResultOut]] = None
    cleanup_targets: Optional[dict[str, Any]] = None
    callback_status: str = "not_requested"
    callback_attempts: int = 0
    finished_at: Optional[datetime] = None
    links: Optional[PushRequestLinks] = None


# ── Error envelope ──

class ErrorDetail(BaseModel):
    field: Optional[str] = None
    suggestion: Optional[str] = None


class GatewayError(BaseModel):
    status: str = "error"
    code: str
    message: str
    details: Optional[ErrorDetail] = None
    trace_id: Optional[str] = None


# ── Integration key management ──

class IntegrationKeyCreate(BaseModel):
    id: str = Field(..., description="Human-readable key ID e.g. 'n8n-vidhi-staging'")
    name: str
    allowed_customer_ids: Optional[list[str]] = None
    allowed_supplier_slugs: Optional[list[str]] = None
    rate_limit_per_minute: int = 60


class IntegrationKeyOut(BaseModel):
    id: str
    name: str
    allowed_customer_ids: Optional[list[str]] = None
    allowed_supplier_slugs: Optional[list[str]] = None
    rate_limit_per_minute: int
    is_active: bool
    last_used_at: Optional[datetime] = None
    created_at: datetime
    revoked_at: Optional[datetime] = None


class IntegrationKeyCreated(IntegrationKeyOut):
    raw_key: str = Field(..., description="Shown once — not stored. Copy immediately.")
