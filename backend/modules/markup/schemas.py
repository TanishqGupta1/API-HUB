from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MarkupRuleCreate(BaseModel):
    customer_id: UUID
    scope: str = "all"
    markup_pct: float
    min_margin: Optional[float] = None
    rounding: str = "none"
    priority: int = 0


class MarkupRuleRead(BaseModel):
    id: UUID
    customer_id: UUID
    scope: str
    markup_pct: float
    min_margin: Optional[float]
    rounding: str
    priority: int
    created_at: datetime

    model_config = {"from_attributes": True}


# -------- push-payload response models --------

class PushVariantPayload(BaseModel):
    sku: Optional[str]
    color: Optional[str]
    size: Optional[str]
    base_price: Optional[float]
    final_price: Optional[float]
    inventory: Optional[int]


class PushImagePayload(BaseModel):
    url: str
    image_type: str


class PushProductMeta(BaseModel):
    supplier_sku: str
    name: str
    brand: Optional[str]
    category: Optional[str]


class AppliedMarkupRule(BaseModel):
    id: UUID
    scope: str
    markup_pct: float
    priority: int


class PushPayload(BaseModel):
    product: PushProductMeta
    variants: list[PushVariantPayload]
    images: list[PushImagePayload]
    markup_rule: Optional[AppliedMarkupRule]
