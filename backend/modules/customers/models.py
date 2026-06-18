import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base, EncryptedJSON


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    name: Mapped[str] = mapped_column(String(255))
    ops_base_url: Mapped[str] = mapped_column(Text)
    ops_token_url: Mapped[str] = mapped_column(Text)
    ops_client_id: Mapped[str] = mapped_column(String(255))
    ops_auth_config: Mapped[dict] = mapped_column(EncryptedJSON, default=dict)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    # ops_auth_config stores: { "client_secret": "..." }
    default_ops_category_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Per-customer default OPS category. Used as the fallback in
    # _build_setProduct_step when a product has no storefront-config category.
    # Without this, products land in OPS with category_id=0 and are hidden
    # from the admin's default browse view (Phase 2 of the OPS push audit).
    # Comma-separated OPS category IDs for the Associated Category field
    # (ProductInput.multiple_category). Products pushed for this customer
    # will appear under all listed categories in addition to the default one.
    ops_associated_category_ids: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # 0 = Print Products section, 1 = Ready to Buy (OPS predefined_product_type). Defaults to 0.
    ops_predefined_product_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
