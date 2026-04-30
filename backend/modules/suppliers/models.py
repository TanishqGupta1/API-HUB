from typing import Optional
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, EncryptedJSON


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    protocol: Mapped[str] = mapped_column(String(50))
    promostandards_code: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    base_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    auth_config: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)
    protocol_config: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=None)
    endpoint_cache: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    endpoint_cache_updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    field_mappings: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True, default=None)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    adapter_class: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    last_full_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_delta_sync: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
