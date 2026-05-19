"""JWT signing + password hashing.

JWT_SECRET_KEY is a separate concern from Fernet SECRET_KEY (database.py).
- Production: JWT_SECRET_KEY must be explicitly set; no fallback.
- Development: falls back to SECRET_KEY with a startup warning.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
from passlib.context import CryptContext

log = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480        # 8 hours (default / non-remember)
REMEMBER_TOKEN_EXPIRE_MINUTES = 1080    # 18 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


def _resolve_jwt_secret() -> str:
    explicit = os.getenv("JWT_SECRET_KEY", "").strip()
    if explicit:
        return explicit
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise RuntimeError(
            "JWT_SECRET_KEY must be set in production. "
            "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(64))\""
        )
    fallback = os.getenv("SECRET_KEY", "").strip()
    if fallback:
        log.warning("JWT_SECRET_KEY unset — falling back to SECRET_KEY (dev only).")
        return fallback
    raise RuntimeError(
        "JWT_SECRET_KEY (or SECRET_KEY as a dev fallback) must be set."
    )


JWT_SECRET_KEY = _resolve_jwt_secret()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(payload: dict[str, Any], *, expire_minutes: int | None = None) -> str:
    minutes = expire_minutes if expire_minutes is not None else ACCESS_TOKEN_EXPIRE_MINUTES
    data = {
        **payload,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
        "type": "access",
    }
    return jwt.encode(data, JWT_SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(payload: dict[str, Any]) -> str:
    data = {
        **payload,
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "type": "refresh",
    }
    return jwt.encode(data, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
