from typing import Any, Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# --- JSONB sub-shapes ---

class PreflightCheck(BaseModel):
    name: str
    ok: bool
    detail: str


class PreflightResults(BaseModel):
    checks: list[PreflightCheck]
    blockers: list[str]        # names of failed checks
    warnings: list[str]
    computed_at: datetime


class ExecutionStep(BaseModel):
    step: int
    mutation: str
    status: str                # "ok" | "failed"
    latency_ms: Optional[int] = None
    response: Optional[dict[str, Any]] = None
    called_at: datetime


class MutationPlanStep(BaseModel):
    step: int
    mutation: str
    variables: dict[str, Any]
    requires_response_from: Optional[list[int]] = None


class ComputedPrice(BaseModel):
    sku: str
    base_price: float
    final_price: float
    markup_pct: float
    rounding: str


class PreviewPayload(BaseModel):
    plan: list[MutationPlanStep]
    computed_prices: list[ComputedPrice]


# --- Top-level request/response models ---

class PushLogCreate(BaseModel):
    product_id: UUID
    customer_id: UUID
    ops_product_id: Optional[str] = None
    status: str
    error: Optional[str] = None


class PushLogRead(BaseModel):
    id: UUID
    product_id: UUID
    product_name: Optional[str] = None
    supplier_name: Optional[str] = None
    customer_id: UUID
    customer_name: Optional[str] = None
    ops_product_id: Optional[str]
    status: str
    error: Optional[str]
    pushed_at: datetime

    # Phase 8 fields (confirm_token_hash excluded — never exposed)
    preflight_results: Optional[PreflightResults] = None
    preview_payload: Optional[PreviewPayload] = None
    preview_built_at: Optional[datetime] = None
    execution_steps: list[ExecutionStep] = []
    cleanup_targets: Optional[dict[str, Any]] = None
    input_hash: Optional[str] = None
    dry_run: bool = False
    confirm_token_consumed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProductPushStatus(BaseModel):
    customer_id: UUID
    customer_name: str
    ops_product_id: Optional[str]
    status: str
    pushed_at: Optional[datetime]
