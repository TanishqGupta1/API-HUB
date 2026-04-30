"""Pydantic models for the manual import endpoint."""
from __future__ import annotations

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .base import DiscoveryMode


class ImportRequest(BaseModel):
    mode: DiscoveryMode = DiscoveryMode.FIRST_N
    limit: Optional[int] = Field(default=20, ge=1, le=10000)
    explicit_list: Optional[list[str]] = None

    @model_validator(mode="after")
    def _check_mode(self) -> "ImportRequest":
        if self.mode == DiscoveryMode.EXPLICIT_LIST and not self.explicit_list:
            raise ValueError("mode=explicit_list requires explicit_list")
        return self


class ImportResponse(BaseModel):
    sync_job_id: UUID
    supplier_id: UUID
    mode: DiscoveryMode
    accepted_at: str   # ISO 8601 timestamp
