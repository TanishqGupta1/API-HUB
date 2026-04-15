from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class MarkupRuleCreate(BaseModel):
    customer_id: UUID
    scope: str = "all"
    markup_pct: float
    min_margin: float | None = None
    rounding: str = "none"
    priority: int = 0


class MarkupRuleRead(BaseModel):
    id: UUID
    customer_id: UUID
    scope: str
    markup_pct: float
    min_margin: float | None
    rounding: str
    priority: int
    created_at: datetime

    model_config = {"from_attributes": True}
