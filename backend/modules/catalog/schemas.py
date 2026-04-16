from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class VariantRead(BaseModel):
    id: UUID
    color: Optional[str]
    size: Optional[str]
    sku: Optional[str]
    base_price: Optional[float]
    inventory: Optional[int]
    warehouse: Optional[str]

    model_config = {"from_attributes": True}


class ProductRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: Optional[str] = None
    supplier_sku: str
    product_name: str
    brand: Optional[str]
    description: Optional[str]
    product_type: str
    image_url: Optional[str]
    last_synced: Optional[datetime]
    variants: list[VariantRead] = []

    model_config = {"from_attributes": True}


class ProductListRead(BaseModel):
    id: UUID
    supplier_id: UUID
    supplier_name: Optional[str] = None
    supplier_sku: str
    product_name: str
    brand: Optional[str]
    product_type: str
    image_url: Optional[str]
    variant_count: int = 0

    model_config = {"from_attributes": True}
