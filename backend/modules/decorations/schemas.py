from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


# The CRUD path stores decoration_options as JSONB freeform — frontend
# decoration-editor sends master-option overlays (option_key/title/attributes),
# tests assert the same shape, and OPS push consumes that shape. Validating
# every key here would couple the storage layer to one consumer, so we accept
# any dict and let the renderer (below) validate its own subset.
DecorationOptionDict = dict[str, Any]


class DecorationCreate(BaseModel):
    decoration_options: list[DecorationOptionDict] = Field(min_length=1)


class DecorationRead(BaseModel):
    customer_id: UUID
    product_id: UUID
    decoration_options: list[DecorationOptionDict]
    updated_at: Optional[datetime] = None  # None when no decoration row exists yet

    model_config = {"from_attributes": True}


class DecorationOption(BaseModel):
    """Layered visual element consumed by the PNG renderer in engine.py.

    Distinct from the master-option overlay shape stored via the CRUD path —
    the renderer's preview.png endpoint validates rows against this model
    explicitly, so persisted records intended for rendering must conform.
    """

    type: str = "logo"
    url: Optional[str] = None
    text: Optional[str] = None
    position_x: float = 0.0
    position_y: float = 0.0
    scale: float = 1.0
    rotation: float = 0.0
    layer: int = 0
