from uuid import UUID
from typing import Optional, Dict, Any
from pydantic import BaseModel, ConfigDict

class ProductStorefrontConfigBase(BaseModel):
    product_id: UUID
    customer_id: UUID
    ops_category_id: Optional[str] = None
    option_mappings: Dict[str, Any] = {}
    pricing_overrides: Dict[str, Any] = {}

class ProductStorefrontConfigUpsert(ProductStorefrontConfigBase):
    pass

class ProductStorefrontConfigRead(ProductStorefrontConfigBase):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
