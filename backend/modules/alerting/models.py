import uuid as uuid_mod
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Notification(Base):
    """In-app notification created by the alerting checker."""

    __tablename__ = "notifications"

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    # push_failed | sync_failed | scheduler_down
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    # error | warning
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="error")
    # Short headline shown in the bell dropdown
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    # Full detail — error message, product/supplier/customer info
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional deep-link into the admin UI (push-log, sync page, etc.)
    link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    # Flipped to True when admin clicks "Dismiss"
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(__import__("datetime").timezone.utc),
    )


class SchedulerHeartbeat(Base):
    """Single-row table — the scheduler writes its timestamp here every cycle.

    The alerting checker reads this to detect a stale / stopped scheduler.
    id is always 1 (upserted on conflict).
    """

    __tablename__ = "scheduler_heartbeat"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    last_ran_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    interval_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(__import__("datetime").timezone.utc),
    )
