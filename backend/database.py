import json
import logging
import os
from pathlib import Path
import base64
import hashlib
from typing import Any, Optional

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from cryptography.fernet import Fernet
from sqlalchemy import Text, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DATABASE_URL = os.getenv(
    "POSTGRES_URL", "postgresql+asyncpg://vg_user:vg_pass@localhost:5432/vg_hub"
)
SECRET_KEY = os.getenv("SECRET_KEY", "")

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _get_fernet() -> Optional[Fernet]:
    """Return a Fernet instance from SECRET_KEY.

    Accepts either a proper Fernet key (urlsafe base64) or an arbitrary string.
    For arbitrary strings, derive a stable Fernet key via SHA-256.
    """
    if not SECRET_KEY:
        return None

    raw = SECRET_KEY.encode()
    try:
        return Fernet(raw)
    except Exception:
        derived = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
        return Fernet(derived)


class EncryptedJSON(TypeDecorator):
    """Transparently encrypts/decrypts JSON data in the database."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> Optional[str]:
        if value is None:
            return None
        f = _get_fernet()
        if not f:
            return json.dumps(value)
        return f.encrypt(json.dumps(value).encode()).decode()

    def process_result_value(self, value: Any, dialect: Any) -> Any:
        if value is None:
            return None
        f = _get_fernet()
        if not f:
            return json.loads(value)
        try:
            return json.loads(f.decrypt(value.encode()))
        except Exception as e:
            # Backwards-compat: if data was stored unencrypted (SECRET_KEY was empty),
            # allow reading it even when SECRET_KEY is now set.
            try:
                return json.loads(value)
            except Exception:
                pass
            logging.error(
                "EncryptedJSON decryption failed — SECRET_KEY mismatch or data corruption: %s",
                e,
            )
            raise ValueError(
                "Failed to decrypt stored secret. Check SECRET_KEY configuration."
            ) from e


async def get_db():
    async with async_session() as session:
        yield session
