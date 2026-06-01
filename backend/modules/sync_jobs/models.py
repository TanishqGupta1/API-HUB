from typing import Optional
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    supplier_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    supplier_name: Mapped[str] = mapped_column(String(255))
    job_type: Mapped[str] = mapped_column(String(50))   # full_sync | inventory | pricing | images | delta
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending | running | success | failed
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    total_products: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    errors: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    discovery_mode: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    alerted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
