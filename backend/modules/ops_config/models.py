import uuid as uuid_mod
from datetime import datetime, timezone
from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, JSON
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

class ProductStorefrontConfig(Base):
    """Stores storefront-specific configuration for a product.
    
    This includes mapping the Hub product to an OPS Category and 
    storing option/attribute mappings.
    """
    __tablename__ = "product_storefront_configs"
    __table_args__ = (
        UniqueConstraint("product_id", "customer_id", name="uq_product_customer_config"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    customer_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # The ID of the category in the remote OPS storefront
    ops_category_id: Mapped[str] = mapped_column(String(100), nullable=True)
    
    # Store mappings of Hub Options -> OPS Master Options
    # Format: { "Color": { "target_ops_option_id": 123, "mappings": { "Navy": 456 } } }
    option_mappings: Mapped[dict] = mapped_column(JSON, default=dict)
    
    # Stores rounding and markup overrides for this specific product + storefront
    pricing_overrides: Mapped[dict] = mapped_column(JSON, default=dict)


class OpsCategoryMapping(Base):
    """Maps a Hub product-category name → an auto-created OPS category id, per
    customer. Lets the push auto-create-or-reuse OPS categories so every product
    lands in its correct category without manual selection.

    `category_key` is the normalized (lower-cased, whitespace-collapsed) product
    category name used for lookup; `category_name` is the display name sent to OPS.
    `external_ref` (e.g. "apihub:cat:polos") links the OPS category back to us.
    """
    __tablename__ = "ops_category_mappings"
    __table_args__ = (
        UniqueConstraint("customer_id", "category_key", name="uq_ops_category_customer_key"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    customer_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_key: Mapped[str] = mapped_column(String(150), nullable=False)
    category_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ops_category_id: Mapped[int] = mapped_column(Integer, nullable=False)
    external_ref: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
