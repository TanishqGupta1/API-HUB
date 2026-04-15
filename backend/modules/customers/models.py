import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, String, Text
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
    # ops_auth_config stores: { "client_secret": "..." }
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
