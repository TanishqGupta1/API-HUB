from typing import Optional
import uuid as uuid_mod
from sqlalchemy import Column, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class CategoryMapping(Base):
    """Maps a supplier category name to an OnPrintShop category ID."""
    __tablename__ = "ops_category_mappings"
    __table_args__ = (
        UniqueConstraint("supplier_id", "source_category", name="uq_ops_category_mapping"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    supplier_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"))
    source_category: Mapped[str] = mapped_column(String(255))  # e.g., "T-Shirts"
    ops_category_id: Mapped[str] = mapped_column(String(100))  # The OPS internal ID


class OptionMapping(Base):
    """Maps a specific supplier option value (e.g., 'Navy') to an OPS attribute ID."""
    __tablename__ = "ops_option_mappings"
    __table_args__ = (
        UniqueConstraint("supplier_id", "option_type", "source_value", name="uq_ops_option_mapping"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    supplier_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"))
    option_type: Mapped[str] = mapped_column(String(50))  # e.g., "color", "size"
    source_value: Mapped[str] = mapped_column(String(255))  # e.g., "Navy Blue"
    ops_attribute_id: Mapped[str] = mapped_column(String(100))  # The OPS internal attribute ID


class ProductConfig(Base):
    """Product-specific overrides for a specific storefront (Customer)."""
    __tablename__ = "ops_product_configs"
    __table_args__ = (
        UniqueConstraint("product_id", "customer_id", name="uq_ops_product_config"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    customer_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("customers.id", ondelete="CASCADE"))
    
    # Overrides
    target_category_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Store the OPS internal Product ID after successful push
    ops_product_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
