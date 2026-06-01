from typing import Optional
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ProductPushLog(Base):
    __tablename__ = "product_push_log"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    customer_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    ops_product_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # status vocab: accepted → queued → processing → pushed | failed | partial_failure | rejected | canceled | dry_run_pushed
    status: Mapped[str] = mapped_column(String(50))
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alerted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    pushed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Phase 8: Integration Gateway — idempotency + tracing
    request_id: Mapped[uuid_mod.UUID] = mapped_column(default=uuid_mod.uuid4, unique=True)
    key_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    payload_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Phase 8: supplier context
    supplier_slug: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    supplier_sku: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Phase 8: callback
    callback_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    callback_status: Mapped[str] = mapped_column(String(32), default="not_requested")
    callback_attempts: Mapped[int] = mapped_column(Integer, default=0)

    # Phase 8: execution tracking (auth headers redacted to "Bearer ***" before write)
    step_results: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    cleanup_targets: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)

    # Phase 8: retry linkage
    retry_of: Mapped[Optional[uuid_mod.UUID]] = mapped_column(nullable=True)

    __table_args__ = (
        Index("idx_push_log_payload_hash", "payload_hash"),
        Index("idx_push_log_idempotency", "key_id", "idempotency_key"),
        # Partial unique index: one active push per (customer, product) at a time
        Index(
            "uq_push_log_in_flight",
            "customer_id", "product_id",
            unique=True,
            postgresql_where=text("status = 'processing'"),
        ),
    )
