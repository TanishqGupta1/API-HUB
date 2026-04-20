from typing import Literal, Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

Protocol = Literal["soap", "rest", "hmac", "ops_graphql", "promostandards"]


class SupplierCreate(BaseModel):
    name: str
    slug: str
    protocol: Protocol
    promostandards_code: Optional[str] = None
    base_url: Optional[str] = None
    auth_config: dict = {}


class SupplierRead(BaseModel):
    id: UUID
    name: str
    slug: str
    protocol: str
    promostandards_code: Optional[str]
    base_url: Optional[str]
    auth_config: dict
    field_mappings: Optional[dict] = None
    is_active: bool
    created_at: datetime
    product_count: int = 0

    model_config = {"from_attributes": True}
