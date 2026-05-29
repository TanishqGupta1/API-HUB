from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, field_validator


class WebhookCreate(BaseModel):
    url: str
    events: list[str] = ["push.completed", "push.failed"]
    secret: Optional[str] = None
    customer_id: Optional[uuid.UUID] = None

    @field_validator("url")
    @classmethod
    def url_must_be_valid(cls, v: str) -> str:
        # Full registration-time SSRF guard (no DNS lookup — deferred to fire time).
        # Reuses the same logic as service._validate_webhook_url.
        from .service import _validate_webhook_url
        try:
            return _validate_webhook_url(v)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("events")
    @classmethod
    def events_must_be_valid(cls, v: list[str]) -> list[str]:
        allowed = {"push.completed", "push.failed", "push.partial_failure"}
        invalid = set(v) - allowed
        if invalid:
            raise ValueError(f"Unknown events: {invalid}. Allowed: {allowed}")
        return v


class WebhookRead(BaseModel):
    id: uuid.UUID
    customer_id: Optional[uuid.UUID]
    url: str
    events: list[str]
    is_active: bool
    failure_count: int
    last_fired_at: Optional[datetime]
    last_failure_at: Optional[datetime]
    created_at: datetime
    has_secret: bool

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, m) -> "WebhookRead":
        return cls(
            id=m.id,
            customer_id=m.customer_id,
            url=m.url,
            events=m.events.split(",") if m.events else [],
            is_active=m.is_active,
            failure_count=m.failure_count,
            last_fired_at=m.last_fired_at,
            last_failure_at=m.last_failure_at,
            created_at=m.created_at,
            has_secret=bool(m.secret),
        )


class WebhookTestResult(BaseModel):
    success: bool
    status_code: Optional[int]
    error: Optional[str]
    fired_at: datetime
