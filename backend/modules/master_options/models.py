import uuid as uuid_mod
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class MasterOption(Base):
    __tablename__ = "master_options"

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    ops_master_option_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    option_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    options_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    pricing_method: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    status: Mapped[int] = mapped_column(Integer, default=1)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    master_option_tag: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    attributes: Mapped[list["MasterOptionAttribute"]] = relationship(
        back_populates="master_option", cascade="all, delete-orphan"
    )


class MasterOptionAttribute(Base):
    __tablename__ = "master_option_attributes"
    __table_args__ = (UniqueConstraint("master_option_id", "ops_attribute_id"),)

    id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid_mod.uuid4
    )
    master_option_id: Mapped[uuid_mod.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("master_options.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ops_attribute_id: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    default_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    raw_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    master_option: Mapped[MasterOption] = relationship(back_populates="attributes")
