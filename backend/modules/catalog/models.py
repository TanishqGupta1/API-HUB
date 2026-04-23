from typing import Optional
import uuid as uuid_mod
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        UniqueConstraint("supplier_id", "external_id", name="uq_category_supplier_external"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    supplier_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("suppliers.id"))
    external_id: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(255))
    parent_id: Mapped[Optional[uuid_mod.UUID]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    products: Mapped[list["Product"]] = relationship(back_populates="category_ref")


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("supplier_id", "supplier_sku", name="uq_product_supplier_sku"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    supplier_id: Mapped[uuid_mod.UUID] = mapped_column(ForeignKey("suppliers.id"))
    supplier_sku: Mapped[str] = mapped_column(String(255))
    product_name: Mapped[str] = mapped_column(String(500))
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    category_id: Mapped[Optional[uuid_mod.UUID]] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    product_type: Mapped[str] = mapped_column(String(50), default="apparel")
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    ops_product_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_catalogue: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    options: Mapped[list["ProductOption"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    category_ref: Mapped[Optional["Category"]] = relationship(back_populates="products")


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "color", "size", name="uq_variant_product_color_size"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    base_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    inventory: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="variants")


class ProductImage(Base):
    __tablename__ = "product_images"
    __table_args__ = (
        UniqueConstraint("product_id", "url", name="uq_product_image_url"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    url: Mapped[str] = mapped_column(Text)
    image_type: Mapped[str] = mapped_column(String(50), default="front")
    color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    product: Mapped["Product"] = relationship(back_populates="images")


class ProductOption(Base):
    __tablename__ = "product_options"
    __table_args__ = (
        UniqueConstraint("product_id", "option_key", name="uq_product_option_key"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    ops_option_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    master_option_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    option_key: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    options_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[int] = mapped_column(Integer, default=1)

    product: Mapped["Product"] = relationship(back_populates="options")
    attributes: Mapped[list["ProductOptionAttribute"]] = relationship(
        back_populates="option", cascade="all, delete-orphan"
    )


class ProductOptionAttribute(Base):
    __tablename__ = "product_option_attributes"
    __table_args__ = (
        UniqueConstraint(
            "product_option_id", "title", name="uq_option_attribute_title"
        ),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_option_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("product_options.id", ondelete="CASCADE")
    )
    ops_attribute_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)

    option: Mapped["ProductOption"] = relationship(back_populates="attributes")
