import hmac
import os
import uuid as uuid_mod
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

from .models import User
from .security import decode_token


# A sentinel "service" user returned for trusted service-to-service calls
# authenticated via X-Ingest-Secret (e.g. n8n → FastAPI). It is never persisted.
_SERVICE_ACCOUNT_ID = uuid_mod.UUID("00000000-0000-0000-0000-000000000001")


def _service_account_user() -> User:
    """Synthetic user representing trusted n8n service calls."""
    user = User()
    user.id = _SERVICE_ACCOUNT_ID
    user.email = "n8n@service.local"
    user.hashed_password = ""
    user.role = "vg_admin"  # service has admin scope (intra-cluster trusted call)
    user.customer_id = None
    user.is_active = True
    return user


def _ingest_secret_matches(provided: str | None) -> bool:
    expected = os.getenv("INGEST_SHARED_SECRET", "").strip()
    if not expected or provided is None:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


async def get_current_user(
    auth_token: Annotated[str | None, Cookie(alias="auth_token")] = None,
    x_ingest_secret: Annotated[str | None, Header(alias="X-Ingest-Secret")] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    # Service-to-service path: trusted n8n container calls send X-Ingest-Secret.
    # Bypass JWT and return a synthetic admin-scoped user.
    if _ingest_secret_matches(x_ingest_secret):
        return _service_account_user()

    if not auth_token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Not authenticated",
            headers={"WWW-Authenticate": "Cookie"},
        )
    try:
        payload = decode_token(auth_token)
        if payload.get("type") != "access":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Invalid or expired token",
            headers={"WWW-Authenticate": "Cookie"},
        )

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def _require_vg_admin(current_user: CurrentUser) -> User:
    if current_user.role != "vg_admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "VG admin access required")
    return current_user


VGAdmin = Annotated[User, Depends(_require_vg_admin)]
