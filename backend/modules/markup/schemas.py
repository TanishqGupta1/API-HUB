from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class MarkupRuleCreate(BaseModel):
    customer_id: UUID
    scope: str = "all"
    markup_pct: Optional[float] = None
    markup_amount: Optional[float] = None
    min_margin: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    rounding: str = "none"
    priority: int = 0
    is_active: bool = True
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None


class MarkupRuleUpdate(BaseModel):
    scope: Optional[str] = None
    markup_pct: Optional[float] = None
    markup_amount: Optional[float] = None
    min_margin: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    rounding: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[bool] = None
    effective_from: Optional[datetime] = None
    effective_until: Optional[datetime] = None


class MarkupRuleRead(BaseModel):
    id: UUID
    customer_id: UUID
    scope: str
    markup_pct: Optional[float]
    markup_amount: Optional[float]
    min_margin: Optional[float]
    min_price: Optional[float]
    max_price: Optional[float]
    rounding: str
    priority: int
    is_active: bool
    effective_from: Optional[datetime]
    effective_until: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
    markup_pct: Optional[float]
    markup_amount: Optional[float]
    priority: int


class PushPayload(BaseModel):
    product: PushProductMeta
    variants: list[PushVariantPayload]
    images: list[PushImagePayload]
    markup_rule: Optional[AppliedMarkupRule]
    # T20 collapse — fields previously served by separate /ops-variants and
    # /ops-options routes are now part of the same /payload response.
    # `ops_variants` mirrors the legacy /ops-variants shape (sizes + prices
    # arrays aligned to the OPS setProductSize / setProductPrice loop).
    # `options` mirrors the legacy /ops-options shape (product-scoped option
    # bundle with master_option_id stripped from the core body).
    ops_variants: "OPSVariantsBundle" = Field(
        default_factory=lambda: OPSVariantsBundle(sizes=[], prices=[])
    )
    options: list["OPSProductOptionSchema"] = Field(default_factory=list)


# -------- OPS variant bundle (n8n setProductSize + setProductPrice loop) --------

class OPSProductSizeInput(BaseModel):
    product_size_id: int = 0        # 0 = create new
    products_id: int                # OPS products_id from prior setProduct call
    size_name: Optional[str]
    color_name: Optional[str]
    products_sku: Optional[str]
    visible: int = 1


class OPSProductPriceEntry(BaseModel):
    product_price_id: int = 0       # 0 = create new
    products_id: int
    qty: int = 1
    qty_to: int = 100
    price: float
    vendor_price: float
    size_id: int = 0                # filled in after setProductSize returns size_id
    visible: str = "1"


class OPSVariantsBundle(BaseModel):
    sizes: list[OPSProductSizeInput]
    prices: list[OPSProductPriceEntry]


# -------- OPS product-scoped option shape (strips master_option_id) --------


class OPSProductAttributeSchema(BaseModel):
    title: str
    price: float = 0.0
    sort_order: int = 0
    numeric_value: float = 0.0
    source_master_attribute_id: Optional[int] = None
    source_attribute_key: Optional[str] = None


class OPSProductOptionSchema(BaseModel):
    option_key: str
    title: str
    options_type: Optional[str] = None
    attributes: list[OPSProductAttributeSchema] = Field(default_factory=list)
    source_master_option_id: Optional[int] = None


# PushPayload forward-references OPSVariantsBundle + OPSProductOptionSchema
# (declared after PushPayload to keep the legacy field order stable for
# any callers that build dicts positionally). Resolve those references now.
PushPayload.model_rebuild()
