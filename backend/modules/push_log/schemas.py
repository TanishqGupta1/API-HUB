from typing import Optional
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PushLogCreate(BaseModel):
    product_id: UUID
    customer_id: UUID
    ops_product_id: Optional[str] = None
    status: str
    error: Optional[str] = None


class PushLogRead(BaseModel):
    id: UUID
    product_id: UUID
    product_name: Optional[str] = None
    supplier_name: Optional[str] = None
    customer_id: UUID
    customer_name: Optional[str] = None
    ops_product_id: Optional[str]
    status: str
    error: Optional[str]
    pushed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductPushStatus(BaseModel):
    customer_id: UUID
    customer_name: str
    ops_product_id: Optional[str]
    status: str
    pushed_at: Optional[datetime]
