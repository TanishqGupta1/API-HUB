from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import Boolean, DateTime, Integer, String, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from database import Base, EncryptedJSON


class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    # Comma-separated event list e.g. "push.completed,push.failed"
    events: Mapped[str] = mapped_column(String(500), nullable=False, default="push.completed,push.failed")
    # HMAC-SHA256 signing secret — stored encrypted via EncryptedJSON (Fernet AES-128, impl=Text).
    # CLAUDE.md: "All credentials via UI, encrypted in DB. Use the EncryptedJSON column type."
    # Shape: {"value": "<raw hmac secret>"} or None. Never exposed in API responses (has_secret bool only).
    # Access the raw string: ep.secret.get("value") if ep.secret else None
    secret: Mapped[Optional[dict]] = mapped_column(EncryptedJSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_fired_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # Use timezone-aware UTC — DateTime(timezone=True) column requires an aware datetime.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
