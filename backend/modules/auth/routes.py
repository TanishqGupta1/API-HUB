import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Response, status
from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

from .dependencies import CurrentUser, VGAdmin
from .models import User
from .schemas import (
    LoginRequest,
    SetupRequest,
    UserCreate,
    UserRead,
)
from .security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REMEMBER_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_COOKIE_NAME = "auth_token"
_COOKIE_SECURE = os.getenv("ENVIRONMENT", "development").lower() == "production"


def _token_payload(user: User) -> dict:
    payload: dict = {
        "sub": str(user.id),
        "email": user.email,
        "role": user.role,
    }
    if user.customer_id:
        payload["customer_id"] = str(user.customer_id)
    return payload


def _set_auth_cookie(response: Response, access_token: str, max_age_minutes: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> None:
    response.set_cookie(
        key=_COOKIE_NAME,
        value=access_token,
        max_age=max_age_minutes * 60,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(key=_COOKIE_NAME, path="/")


@router.post("/login", response_model=UserRead)
async def login(
    body: LoginRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    payload = _token_payload(user)
    expire = REMEMBER_TOKEN_EXPIRE_MINUTES if body.remember_me else ACCESS_TOKEN_EXPIRE_MINUTES
    _set_auth_cookie(response, create_access_token(payload, expire_minutes=expire), max_age_minutes=expire)
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    _clear_auth_cookie(response)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser):
    return current_user


@router.post("/setup", response_model=UserRead, status_code=201)
async def setup_first_admin(
    body: SetupRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    """Create the first vg_admin. Returns 409 if any user already exists.

    Race-safe via INSERT ... ON CONFLICT DO NOTHING on the email unique
    constraint.
    """
    count = (await db.execute(select(func.count()).select_from(User))).scalar()
    if count and count > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Admin already configured")

    stmt = (
        pg_insert(User)
        .values(
            email=body.email,
            hashed_password=hash_password(body.password),
            role="vg_admin",
        )
        .on_conflict_do_nothing(index_elements=[User.email])
        .returning(User)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()
    await db.commit()
    if not user:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")

    payload = _token_payload(user)
    _set_auth_cookie(response, create_access_token(payload))
    return user


@router.post("/users", response_model=UserRead, status_code=201)
async def create_user(body: UserCreate, _: VGAdmin, db: AsyncSession = Depends(get_db)) -> User:
    # role/customer_id consistency enforced by UserCreate.model_validator
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
        customer_id=body.customer_id,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    await db.refresh(user)
    return user


@router.get("/users", response_model=list[UserRead])
async def list_users(_: VGAdmin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str, current_admin: VGAdmin, db: AsyncSession = Depends(get_db)
) -> None:
    if str(current_admin.id) == user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete your own account")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await db.delete(user)
    await db.commit()
