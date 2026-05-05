from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

from .dependencies import CurrentUser, VGAdmin
from .models import User
from .schemas import (
    LoginRequest,
    RefreshRequest,
    SetupRequest,
    TokenResponse,
    UserCreate,
    UserRead,
)
from .security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _token_payload(user: User) -> dict:
    payload: dict = {"sub": str(user.id), "email": user.email, "role": user.role}
    if user.customer_id:
        payload["customer_id"] = str(user.customer_id)
    return payload


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    payload = _token_payload(user)
    return TokenResponse(
        access_token=create_access_token(payload),
        refresh_token=create_refresh_token(payload),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type")
        user_id = payload.get("sub")
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found")

    new_payload = _token_payload(user)
    return TokenResponse(
        access_token=create_access_token(new_payload),
        refresh_token=create_refresh_token(new_payload),
    )


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser):
    return current_user


@router.post("/setup", response_model=UserRead, status_code=201)
async def setup_first_admin(body: SetupRequest, db: AsyncSession = Depends(get_db)):
    """Creates the first VG admin. Returns 409 if any users already exist."""
    count = (await db.execute(select(func.count()).select_from(User))).scalar()
    if count and count > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Admin already configured")
    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role="vg_admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.post("/users", response_model=UserRead, status_code=201)
async def create_user(body: UserCreate, _: VGAdmin, db: AsyncSession = Depends(get_db)):
    existing = (
        await db.execute(select(User).where(User.email == body.email))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT, "Email already registered")
    if body.role == "customer_admin" and not body.customer_id:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "customer_admin requires customer_id")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        role=body.role,
        customer_id=body.customer_id,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.get("/users", response_model=list[UserRead])
async def list_users(_: VGAdmin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    return result.scalars().all()


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(user_id: str, current_admin: VGAdmin, db: AsyncSession = Depends(get_db)):
    if str(current_admin.id) == user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete your own account")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await db.delete(user)
    await db.commit()
