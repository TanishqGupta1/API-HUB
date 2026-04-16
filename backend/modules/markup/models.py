from typing import Optional
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class MarkupRule(Base):
    __tablename__ = "markup_rules"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    customer_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    scope: Mapped[str] = mapped_column(String(50), default="all")
    # scope values: "all", "category:{name}", "product:{supplier_sku}"
    markup_pct: Mapped[float] = mapped_column(Numeric(5, 2))
    # e.g. 45.00 = 45% markup over base_price
    min_margin: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    rounding: Mapped[str] = mapped_column(String(20), default="none")
    # rounding values: "none", "nearest_99", "nearest_dollar"
    priority: Mapped[int] = mapped_column(Integer, default=0)
    # higher priority wins when multiple rules match
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
