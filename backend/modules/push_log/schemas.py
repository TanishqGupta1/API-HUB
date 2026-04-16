from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PushLogCreate(BaseModel):
    product_id: UUID
    customer_id: UUID
    ops_product_id: str | None = None
    status: str
    error: str | None = None


class PushLogRead(BaseModel):
    id: UUID
    product_id: UUID
    product_name: str | None = None
    supplier_name: str | None = None
    customer_id: UUID
    customer_name: str | None = None

    ops_product_id: str | None
    status: str
    error: str | None
    pushed_at: datetime

    model_config = {"from_attributes": True}


class ProductPushStatus(BaseModel):
    customer_id: UUID
    customer_name: str
    ops_product_id: str | None
    status: str
    pushed_at: datetime | None
