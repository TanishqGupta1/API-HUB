from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

from .models import User
from .security import decode_token


async def get_current_user(
    auth_token: Annotated[str | None, Cookie(alias="auth_token")] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
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
