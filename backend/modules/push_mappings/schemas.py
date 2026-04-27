from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PushMappingOptionIngest(BaseModel):
    source_master_option_id: Optional[int] = None
    source_master_attribute_id: Optional[int] = None
    source_option_key: Optional[str] = None
    source_attribute_key: Optional[str] = None
    target_ops_option_id: Optional[int] = None
    target_ops_attribute_id: Optional[int] = None
    title: str
    price: Decimal = Decimal("0.00")
    sort_order: int = 0


class PushMappingUpsert(BaseModel):
    source_system: str
    source_product_id: UUID
    source_supplier_sku: Optional[str] = None
    customer_id: UUID
    target_ops_base_url: str
    target_ops_product_id: int
    options: list[PushMappingOptionIngest]


class PushMappingOptionRead(PushMappingOptionIngest):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    push_mapping_id: UUID
    created_at: datetime


class PushMappingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_system: str
    source_product_id: UUID
    source_supplier_sku: Optional[str] = None
    customer_id: UUID
    target_ops_base_url: str
    target_ops_product_id: int
    pushed_at: datetime
    updated_at: datetime
    status: str
    options: list[PushMappingOptionRead]


# Outbound OPS shape (product-scoped)
class OPSProductAttribute(BaseModel):
    title: str
    price: Decimal = Decimal("0.00")
    sort_order: int = 0


class OPSProductOption(BaseModel):
    option_key: str
    title: str
    options_type: str = "combo"
    attributes: list[OPSProductAttribute]
