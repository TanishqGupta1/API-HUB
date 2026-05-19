from typing import Any, Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# --- JSONB sub-shapes ---

class StepResult(BaseModel):
    step: Any  # int or str depending on gateway version
    ok: bool = True
    ops_id: Optional[str] = None
    ops_ids: Optional[dict[str, Any]] = None
    status: Optional[str] = None
    mutation: Optional[str] = None
    error: Optional[str] = None
    latency_ms: Optional[int] = None
    called_at: Optional[datetime] = None
    attempted_at: Optional[str] = None
    request_fingerprint: Optional[str] = None
    source_key: Optional[str] = None


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
    pushed_at: Optional[datetime] = None

    # Integration Gateway fields
    request_id: Optional[UUID] = None
    key_id: Optional[str] = None
    idempotency_key: Optional[str] = None
    payload_hash: Optional[str] = None
    supplier_slug: Optional[str] = None
    supplier_sku: Optional[str] = None
    callback_url: Optional[str] = None
    callback_status: str = "not_requested"
    callback_attempts: int = 0
    step_results: Optional[list[StepResult]] = None
    cleanup_targets: Optional[dict[str, Any]] = None
    dry_run: bool = False
    retry_of: Optional[UUID] = None

    model_config = ConfigDict(from_attributes=True)


class PushRequestResponse(BaseModel):
    push_log_id: UUID
    status: str
    customer_id: UUID
    supplier_slug: Optional[str] = None
    supplier_sku: Optional[str] = None
    ops_product_id: Optional[str] = None
    dry_run: bool = False
    callback_status: str = "not_requested"
    created_at: datetime
    links: dict[str, str] = {}


class PushStatusResponse(BaseModel):
    push_log_id: UUID
    status: str
    customer_id: UUID
    supplier_slug: Optional[str] = None
    supplier_sku: Optional[str] = None
    ops_product_id: Optional[str] = None
    error: Optional[str] = None
    step_results: Optional[list[StepResult]] = None
    cleanup_targets: Optional[dict[str, Any]] = None
    callback_status: str = "not_requested"
    callback_attempts: int = 0
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ProductPushStatus(BaseModel):
    customer_id: UUID
    customer_name: str
    ops_product_id: Optional[str]
    status: str
    pushed_at: Optional[datetime]
