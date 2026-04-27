import json
import logging
import os
from pathlib import Path
import base64
import hashlib
from typing import Any, Optional

from dotenv import load_dotenv
_dotenv_path = Path(__file__).parent.parent / ".env"
if _dotenv_path.exists():
    load_dotenv(_dotenv_path)

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import Text, TypeDecorator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

log = logging.getLogger(__name__)

DATABASE_URL = os.getenv("POSTGRES_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "POSTGRES_URL environment variable is required. "
        "Set it via .env for local dev or via container env/Secrets Manager in production."
    )
SECRET_KEY = os.getenv("SECRET_KEY", "")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
ALLOW_UNENCRYPTED_LEGACY = os.getenv("ALLOW_UNENCRYPTED_LEGACY", "").lower() in {"1", "true", "yes"}

_MIN_DERIVED_KEY_LEN = 32

engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def _get_fernet() -> Optional[Fernet]:
    """Return a Fernet instance from SECRET_KEY.

    Accepts a proper urlsafe-base64 Fernet key directly. In non-production
    environments, a long arbitrary string is accepted and a stable Fernet key
    is derived from it via SHA-256. In production, only real Fernet keys are
    accepted — weak SECRET_KEY values must be rejected at startup.
    """
    if not SECRET_KEY:
        return None

    raw = SECRET_KEY.encode()
    try:
        return Fernet(raw)
    except (ValueError, TypeError):
        if ENVIRONMENT == "production":
            raise RuntimeError(
                "SECRET_KEY is not a valid Fernet key. "
                "Generate one with: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
            )
        if len(raw) < _MIN_DERIVED_KEY_LEN:
            raise RuntimeError(
                f"SECRET_KEY is too short ({len(raw)} < {_MIN_DERIVED_KEY_LEN}). "
                "Use a real Fernet key or a long random string."
            )
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
            if ENVIRONMENT == "production":
                raise RuntimeError(
                    "SECRET_KEY is required in production — refusing to write unencrypted secret."
                )
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
        except InvalidToken:
            if ALLOW_UNENCRYPTED_LEGACY:
                try:
                    parsed = json.loads(value)
                except ValueError:
                    raise ValueError(
                        "Stored secret is neither valid Fernet ciphertext nor legacy JSON."
                    )
                log.warning(
                    "EncryptedJSON: read UNENCRYPTED legacy row (ALLOW_UNENCRYPTED_LEGACY=1). "
                    "Re-save the row to encrypt it at rest."
                )
                return parsed
            log.error(
                "EncryptedJSON decryption failed — SECRET_KEY mismatch, rotated key, or unencrypted legacy row. "
                "Set ALLOW_UNENCRYPTED_LEGACY=1 to permit migration reads."
            )
            raise ValueError(
                "Failed to decrypt stored secret. Check SECRET_KEY configuration "
                "or set ALLOW_UNENCRYPTED_LEGACY=1 to migrate legacy rows."
            )


async def get_db():
    async with async_session() as session:
        yield session
