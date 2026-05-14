from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class IntegrationKey(Base):
    __tablename__ = "integration_keys"

    # Human-readable key ID shown in UI (e.g. "n8n-vidhi-staging")
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    # SHA-256 of raw key — raw key shown once at creation, never stored
    key_hash: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255))

    # Scope — null means unrestricted
    allowed_customer_ids: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    allowed_supplier_slugs: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    rate_limit_per_minute: Mapped[int] = mapped_column(Integer, default=60)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
