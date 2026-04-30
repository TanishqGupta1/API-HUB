from typing import Optional
import uuid as uuid_mod
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
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
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

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
    apparel_details: Mapped[Optional["ApprelDetails"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", uselist=False
    )
    print_details: Mapped[Optional["PrintDetails"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", uselist=False
    )
    sizes: Mapped[list["ProductSize"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"
    __table_args__ = (
        UniqueConstraint("product_id", "color", "size", name="uq_variant_product_color_size"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    color: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    size: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    sku: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    base_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    inventory: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    warehouse: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="variants")
    prices: Mapped[list["VariantPrice"]] = relationship(
        back_populates="variant", cascade="all, delete-orphan"
    )


class ProductImage(Base):
    __tablename__ = "product_images"
    __table_args__ = (
        UniqueConstraint("product_id", "url", name="uq_product_image_url"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
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
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    ops_option_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    master_option_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    option_key: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    options_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    required: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    overridden_sort: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

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
    master_attribute_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    attribute_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    setup_cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    multiplier: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    numeric_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    overridden_sort: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    option: Mapped["ProductOption"] = relationship(back_populates="attributes")


class ApprelDetails(Base):
    __tablename__ = "apparel_details"

    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    pricing_method: Mapped[str] = mapped_column(String(50), default="tiered_variant")
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="apparel_details")


class PrintDetails(Base):
    __tablename__ = "print_details"

    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), primary_key=True
    )
    pricing_method: Mapped[str] = mapped_column(String(50), default="formula")
    min_width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    max_width: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    min_height: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    max_height: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    size_unit: Mapped[str] = mapped_column(String(10), default="in")
    base_price_per_sq_unit: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    product: Mapped["Product"] = relationship(back_populates="print_details")


class VariantPrice(Base):
    __tablename__ = "variant_prices"
    __table_args__ = (
        UniqueConstraint("variant_id", "price_type", "quantity_min", name="uq_variant_price_type_qty"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    variant_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("product_variants.id", ondelete="CASCADE"), index=True
    )
    price_type: Mapped[str] = mapped_column(String(20))  # MSRP | Net | Sale | Case
    quantity_min: Mapped[int] = mapped_column(Integer)
    quantity_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    variant: Mapped["ProductVariant"] = relationship(back_populates="prices")


class ProductSize(Base):
    __tablename__ = "product_sizes"
    __table_args__ = (
        UniqueConstraint("product_id", "width", "height", name="uq_product_size_wh"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"), index=True
    )
    width: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    height: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit: Mapped[str] = mapped_column(String(10), default="in")
    label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    product: Mapped["Product"] = relationship(back_populates="sizes")
