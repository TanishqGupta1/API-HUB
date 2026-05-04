from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from modules.catalog.schemas import OptionIngest


class DecorationCreate(BaseModel):
    decoration_options: list[OptionIngest] = Field(min_length=1)


class DecorationRead(BaseModel):
    customer_id: UUID
    product_id: UUID
    decoration_options: list[OptionIngest]
    updated_at: datetime

    model_config = {"from_attributes": True}
