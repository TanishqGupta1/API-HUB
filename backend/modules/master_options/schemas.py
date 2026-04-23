from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


# ---- Read (for GET /api/master-options) ----

class MasterOptionAttributeRead(BaseModel):
    id: UUID
    ops_attribute_id: int
    title: str
    sort_order: int
    default_price: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class MasterOptionRead(BaseModel):
    id: UUID
    ops_master_option_id: int
    title: str
    option_key: Optional[str] = None
    options_type: Optional[str] = None
    pricing_method: Optional[str] = None
    status: int
    sort_order: int
    description: Optional[str] = None
    master_option_tag: Optional[str] = None
    attributes: list[MasterOptionAttributeRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


# ---- Ingest (for POST /api/ingest/master-options — n8n payload) ----

class MasterOptionAttributeIngest(BaseModel):
    ops_attribute_id: int
    title: str
    sort_order: int = 0
    default_price: Optional[Decimal] = None
    raw_json: Optional[dict] = None


class MasterOptionIngest(BaseModel):
    ops_master_option_id: int
    title: str
    option_key: Optional[str] = None
    options_type: Optional[str] = None
    pricing_method: Optional[str] = None
    status: int = 1
    sort_order: int = 0
    description: Optional[str] = None
    master_option_tag: Optional[str] = None
    attributes: list[MasterOptionAttributeIngest] = Field(default_factory=list)
    raw_json: Optional[dict] = None


# ---- Per-product config (GET/PUT /api/products/{id}/options-config) ----

class AttributeConfigItem(BaseModel):
    attribute_id: Optional[UUID] = None
    ops_attribute_id: int
    title: str
    attribute_key: Optional[str] = None
    enabled: bool = False
    price: Decimal = Decimal("0")
    numeric_value: Decimal = Decimal("0")
    sort_order: int = 0


class OptionConfigItem(BaseModel):
    master_option_id: UUID
    ops_master_option_id: int
    title: str
    option_key: Optional[str] = None
    options_type: Optional[str] = None
    master_option_tag: Optional[str] = None
    enabled: bool = False
    attributes: list[AttributeConfigItem] = Field(default_factory=list)


class SyncStatus(BaseModel):
    total: int
    last_synced_at: Optional[str] = None
