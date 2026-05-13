from typing import Optional
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class ProductPushLog(Base):
    __tablename__ = "product_push_log"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    customer_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    ops_product_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # status vocab: pending → preview_ready → executing → dry_run_pushed | pushed | failed
    status: Mapped[str] = mapped_column(String(50))
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pushed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Phase 8: preflight + preview state
    preflight_results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    preview_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    preview_built_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Phase 8: execution tracking
    execution_steps: Mapped[list] = mapped_column(JSONB, default=list)
    cleanup_targets: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    dry_run: Mapped[bool] = mapped_column(Boolean, default=False)

    # Phase 8: confirm token (hash only — plaintext never persisted)
    input_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confirm_token_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    confirm_token_consumed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("idx_push_log_input_hash", "input_hash"),
        # Partial unique index: only one executing push per (customer, product) at a time
        Index(
            "uq_push_log_in_flight",
            "customer_id", "product_id",
            unique=True,
            postgresql_where=text("status = 'executing'"),
        ),
    )
