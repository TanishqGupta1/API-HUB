import uuid as uuid_mod
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class PushMapping(Base):
    __tablename__ = "push_mappings"
    __table_args__ = (
        UniqueConstraint("source_product_id", "customer_id", name="uq_push_mapping_product_customer"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    source_system: Mapped[str] = mapped_column(String(50), nullable=False)
    source_product_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_supplier_sku: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    target_ops_base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    target_ops_product_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    pushed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active")

    options: Mapped[list["PushMappingOption"]] = relationship(
        back_populates="push_mapping", cascade="all, delete-orphan"
    )


class PushMappingOption(Base):
    __tablename__ = "push_mapping_options"

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    push_mapping_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("push_mappings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_master_option_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_master_attribute_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_option_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    source_attribute_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_ops_option_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    target_ops_attribute_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    sort_order: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    push_mapping: Mapped[PushMapping] = relationship(back_populates="options")
