from typing import Optional
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class MarkupRule(Base):
    __tablename__ = "markup_rules"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    customer_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(50), default="all")
    # scope values: "all", "category:{name}", "product:{supplier_sku}", "supplier:{slug}"
    markup_pct: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    # e.g. 45.00 = 45% markup over base_price
    markup_amount: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    # Fixed dollar markup — mutually exclusive with markup_pct (UI enforces)
    min_margin: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    min_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    # Absolute floor — final price never goes below this
    max_price: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    # Absolute ceiling — final price never exceeds this
    rounding: Mapped[str] = mapped_column(String(20), default="none")
    # rounding values: "none", "nearest_99", "nearest_dollar"
    priority: Mapped[int] = mapped_column(Integer, default=0)
    # higher priority wins when multiple rules match
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Toggle rule on/off without deleting
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # If set, rule only applies after this timestamp
    effective_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # If set, rule expires after this timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
