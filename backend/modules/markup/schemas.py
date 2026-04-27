from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


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
