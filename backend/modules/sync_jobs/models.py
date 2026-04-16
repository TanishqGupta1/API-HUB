from typing import Optional
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    supplier_id: Mapped[uuid_mod.UUID] = mapped_column(nullable=False)
    supplier_name: Mapped[str] = mapped_column(String(255))
    job_type: Mapped[str] = mapped_column(String(50))   # full_sync | inventory | pricing | images | delta
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending | running | completed | failed
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    records_processed: Mapped[int] = mapped_column(Integer, default=0)
    error_log: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
