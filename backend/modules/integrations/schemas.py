"""Integration Gateway envelope schemas.

Names follow the Rev 3 spec (`docs/superpowers/specs/2026-05-13-centralized-
fastapi-ops-design.md`): `PushRequestTarget`, `PushRequestSource`,
`PushRequestProductRef`, `PushRequestCallback`, `PushRequest`,
`PushRequestAccepted`, `PushRequestStatus`, `ErrorEnvelope`.

Short aliases (`PushTarget`, `PushSource`, `PushProductRef`, `PushCallback`,
`PushStatusOut`, `GatewayError`) are kept for backwards compatibility with
existing call sites (`routes.py`, `modules.ops_push.gateway`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, Union
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


# ── Push request envelope ──

class PushRequestTarget(BaseModel):
    system: Literal["ops"] = "ops"
    customer_id: UUID


class PushRequestSource(BaseModel):
    supplier_slug: str


class PushRequestProductRef(BaseModel):
    """Identify the product to push by either internal UUID or supplier SKU.

    At least one of `product_id` / `supplier_sku` must be set — the gateway
    resolves the canonical product row from whichever is supplied. We don't
    enforce the "at least one" rule at the schema layer because the spec
    leaves room for future ref types (e.g. external SKU); the resolver
    raises if neither is usable.
    """

    product_id: Optional[UUID] = None
    supplier_sku: Optional[str] = None


class PushRequestCallback(BaseModel):
    url: str
    secret: Optional[str] = None


class PushRequest(BaseModel):
    target: PushRequestTarget
    source: PushRequestSource
    product_ref: PushRequestProductRef
    product: Optional[dict[str, Any]] = None   # inline upsert (future)
    decorations: list[dict[str, Any]] = Field(default_factory=list)
    dry_run: bool = False
    callback: Optional[PushRequestCallback] = None


# ── Push responses ──

class PushRequestLinks(BaseModel):
    self: str


class PushRequestAccepted(BaseModel):
    push_log_id: UUID
    status: str
    customer_id: UUID
    supplier_slug: str
    supplier_sku: Optional[str] = None
    ops_product_id: Optional[str] = None
    dry_run: bool = False
    callback_status: str = "not_requested"
    created_at: datetime
    links: PushRequestLinks


class StepResultOut(BaseModel):
    step: Union[str, int]
    ok: bool = True
    status: Optional[str] = None  # "ok" | "failed" — gateway writes this
    mutation: Optional[str] = None
    source_key: Optional[str] = None
    ops_ids: Optional[dict] = None   # gateway writes ops_ids (dict), not ops_id (str)
    ops_id: Optional[str] = None     # legacy field — kept for backwards compat
    error: Optional[str] = None
    latency_ms: Optional[int] = None
    attempted_at: Optional[str] = None
    request_fingerprint: Optional[str] = None

    @model_validator(mode="after")
    def _derive_ok_from_status(self) -> "StepResultOut":
        if self.status is not None:
            object.__setattr__(self, "ok", self.status == "ok")
        return self


class PushRequestStatus(BaseModel):
    """Spec-named poll-response envelope (GET /push-requests/{id})."""

    push_log_id: UUID
    status: str
    customer_id: UUID
    supplier_slug: Optional[str] = None
    supplier_sku: Optional[str] = None
    ops_product_id: Optional[str] = None
    mapping_id: Optional[UUID] = None
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


class ErrorEnvelope(BaseModel):
    """Spec name for the gateway error envelope. `details` is an open dict
    so each error code can attach its own structured context (e.g.
    PREFLIGHT_BLOCKER carries missing[], IDEMPOTENCY_CONFLICT carries the
    diverging payload hash)."""

    status: Literal["error"] = "error"
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
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


# ── Backwards-compat aliases (do not remove without sweeping call sites) ──

PushTarget = PushRequestTarget
PushSource = PushRequestSource
PushProductRef = PushRequestProductRef
PushCallback = PushRequestCallback
PushStatusOut = PushRequestStatus
GatewayError = ErrorEnvelope
