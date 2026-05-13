from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from typing import Optional

class DecorationOption(BaseModel):
    type: str = "logo"
    url: Optional[str] = None
    text: Optional[str] = None
    position_x: float = 0.0
    position_y: float = 0.0
    scale: float = 1.0
    rotation: float = 0.0
    layer: int = 0


class DecorationCreate(BaseModel):
    decoration_options: list[DecorationOption] = Field(min_length=1)


class DecorationRead(BaseModel):
    customer_id: UUID
    product_id: UUID
    decoration_options: list[DecorationOption]
    updated_at: datetime

    model_config = {"from_attributes": True}
