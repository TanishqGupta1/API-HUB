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
REFRESH_TOKEN_EXPIRE_MINUTES = 7 * 24 * 60  # 7 days


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
    """Create a long-lived refresh token (7 days).

    Refresh tokens carry minimal claims — only ``sub``, ``type=refresh``, and
    ``exp``.  They are stored in a separate ``refresh_token`` HttpOnly cookie
    so a compromised access token cannot be used to mint new access tokens.
    """
    data = {
        "sub": payload["sub"],
        "exp": datetime.now(timezone.utc) + timedelta(minutes=REFRESH_TOKEN_EXPIRE_MINUTES),
        "type": "refresh",
    }
    return jwt.encode(data, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str, *, expected_type: str | None = None) -> dict[str, Any]:
    """Decode and validate a JWT.

    Args:
        token: The raw JWT string.
        expected_type: If provided, raises JWTError when token ``type`` claim
            does not match (e.g. ``"refresh"`` to guard the refresh endpoint).
    """
    claims = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
    if expected_type is not None and claims.get("type") != expected_type:
        from jose import JWTError
        raise JWTError(f"Expected token type '{expected_type}', got '{claims.get('type')}'")
    return claims
