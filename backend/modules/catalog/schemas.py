from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class VariantRead(BaseModel):
    id: UUID
    color: str | None
    size: str | None
    sku: str | None
    base_price: float | None
    inventory: int | None
    warehouse: str | None

    model_config = {"from_attributes": True}


class ProductRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str | None = None
    supplier_sku: str
    product_name: str
    brand: str | None
    description: str | None
    product_type: str
    image_url: str | None
    last_synced: datetime | None
    variants: list[VariantRead] = []

    model_config = {"from_attributes": True}


class ProductListRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: str | None = None
    supplier_sku: str
    product_name: str
    brand: str | None
    product_type: str
    image_url: str | None
    variant_count: int = 0

    model_config = {"from_attributes": True}
