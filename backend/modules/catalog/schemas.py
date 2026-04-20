from typing import Optional
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class VariantRead(BaseModel):
    id: UUID
    color: Optional[str]
    size: Optional[str]
    sku: Optional[str]
    base_price: Optional[float]
    inventory: Optional[int]
    warehouse: Optional[str]

    model_config = {"from_attributes": True}


class ProductImageRead(BaseModel):
    id: UUID
    url: str
    image_type: str
    color: Optional[str]
    sort_order: int

    model_config = {"from_attributes": True}


class ProductRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: Optional[str] = None
    supplier_sku: str
    product_name: str
    brand: Optional[str]
    category: Optional[str]
    description: Optional[str]
    product_type: str
    image_url: Optional[str]
    ops_product_id: Optional[str]
    last_synced: Optional[datetime]
    variants: list[VariantRead] = []
    images: list[ProductImageRead] = []

    model_config = {"from_attributes": True}


class ProductListRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: Optional[str] = None
    supplier_sku: str
    product_name: str
    brand: Optional[str]
    category: Optional[str]
    category_id: Optional[UUID] = None
    product_type: str
    image_url: Optional[str]
    variant_count: int = 0

    model_config = {"from_attributes": True}


# ---------- Ingest schemas (used by POST /api/ingest/{supplier_id}/...) ----------
#
# Shape mirrors PSProductData / PSInventoryLevel / PSPricePoint so every supplier
# (SanMar SOAP, S&S REST, 4Over HMAC, VG OPS GraphQL) feeds the same contract.


class VariantIngest(BaseModel):
    part_id: str
    color: Optional[str] = None
    size: Optional[str] = None
    sku: Optional[str] = None
    base_price: Optional[Decimal] = None
    inventory: Optional[int] = None
    warehouse: Optional[str] = None


class ImageIngest(BaseModel):
    url: str
    image_type: str = "front"
    color: Optional[str] = None
    sort_order: int = 0


class ProductIngest(BaseModel):
    supplier_sku: str
    product_name: str
    brand: Optional[str] = None
    description: Optional[str] = None
    product_type: str = "apparel"
    image_url: Optional[str] = None
    ops_product_id: Optional[str] = None
    category_external_id: Optional[str] = None
    category_name: Optional[str] = None
    variants: list[VariantIngest] = Field(default_factory=list)
    images: list[ImageIngest] = Field(default_factory=list)


class InventoryIngest(BaseModel):
    supplier_sku: str
    part_id: str
    quantity_available: int = 0
    warehouse: Optional[str] = None


class PriceIngest(BaseModel):
    supplier_sku: str
    part_id: str
    base_price: Decimal


class CategoryIngest(BaseModel):
    external_id: str
    name: str
    parent_external_id: Optional[str] = None
    sort_order: int = 0


class IngestResult(BaseModel):
    sync_job_id: UUID
    records_processed: int
    status: str
