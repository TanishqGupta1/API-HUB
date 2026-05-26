import logging
import os
import uuid as uuid_mod

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from limiter import limiter
from jose import JWTError
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

from .dependencies import CurrentUser, VGAdmin
from .models import AppSetting, User
from .schemas import (
    LoginRequest,
    SetupRequest,
    SignupSettings,
    UserCreate,
    UserRead,
)
from .security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REMEMBER_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

_COOKIE_NAME = "auth_token"
_REFRESH_COOKIE_NAME = "refresh_token"
_COOKIE_SECURE = os.getenv("ENVIRONMENT", "development").lower() == "production"
# Pre-computed bcrypt hash of a random throw-away password. Used by login when
# the email lookup misses, so a bcrypt verify still runs and timing stays
# constant regardless of whether the email exists.
_DUMMY_HASH = hash_password("$dummy-for-timing$do-not-use$")

_SIGNUP_SETTING_KEY = "signup_enabled"


async def _is_signup_enabled(db: AsyncSession) -> bool:
    """DEPRECATED — no longer gates registration (bootstrap-only now). Read
    only by the legacy /settings/signup endpoints; grants no access. Remove
    with those endpoints + their frontend toggle in a follow-up PR."""
    setting = await db.get(AppSetting, _SIGNUP_SETTING_KEY)
    if setting is None:
        return False
    return bool(setting.value.get("enabled", False))


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
        samesite="strict" if _COOKIE_SECURE else "lax",
        path="/",
    )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=_REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="strict",   # stricter: refresh endpoint is same-origin only
        path="/api/auth/refresh",
    )


def _clear_auth_cookie(response: Response) -> None:
    # RFC 6265 / browser compat: delete_cookie must echo the same path,
    # samesite, and secure flags used on set_cookie. Without them Safari
    # and Firefox strict-mode won't clear cross-site cookies on logout.
    response.delete_cookie(
        key=_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="lax",
    )
    response.delete_cookie(
        key=_REFRESH_COOKIE_NAME,
        path="/api/auth/refresh",
        httponly=True,
        secure=_COOKIE_SECURE,
        samesite="strict",
    )


@router.post("/login", response_model=UserRead)
@limiter.limit("10/minute")
async def login(
    request: Request,  # required by slowapi — do not remove
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    result = await db.execute(
        select(User).where(User.email == body.email, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    # Always run a bcrypt verify so response time doesn't reveal whether the
    # email exists (timing-safe lookup).
    password_ok = verify_password(body.password, user.hashed_password if user else _DUMMY_HASH)
    if not user or not password_ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")

    payload = _token_payload(user)
    expire = REMEMBER_TOKEN_EXPIRE_MINUTES if body.remember_me else ACCESS_TOKEN_EXPIRE_MINUTES
    _set_auth_cookie(response, create_access_token(payload, expire_minutes=expire), max_age_minutes=expire)
    _set_refresh_cookie(response, create_refresh_token(payload))
    return user


@router.post("/refresh", response_model=UserRead)
@limiter.limit("30/minute")
async def refresh_access_token(
    request: Request,  # required by slowapi — do not remove
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Exchange a valid refresh_token cookie for a new access_token cookie.

    The refresh token is bound to the ``/api/auth/refresh`` path via a
    ``SameSite=Strict`` cookie so it cannot be sent cross-origin.  On success
    a fresh access token is issued; the refresh token itself is rotated to
    extend its lifetime.
    """
    raw = request.cookies.get(_REFRESH_COOKIE_NAME)
    if not raw:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token missing")
    try:
        claims = decode_token(raw, expected_type="refresh")
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired refresh token")

    # Validate sub as UUID before DB query — malformed sub would cause a 500.
    try:
        user_id = uuid_mod.UUID(claims["sub"])
    except (ValueError, KeyError, TypeError):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token claims")

    result = await db.execute(
        select(User).where(User.id == user_id, User.is_active.is_(True))
    )
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found or deactivated")

    payload = _token_payload(user)
    _set_auth_cookie(response, create_access_token(payload))
    _set_refresh_cookie(response, create_refresh_token(payload))  # rotate
    return user


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    _clear_auth_cookie(response)


@router.get("/me", response_model=UserRead)
async def get_me(current_user: CurrentUser):
    return current_user


@router.post("/setup", response_model=UserRead, status_code=201)
@limiter.limit("5/minute")
async def setup_first_admin(
    request: Request,  # required by slowapi — do not remove
    body: SetupRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    """Create the first vg_admin. Returns 409 if ANY user already exists.

    The count guard is the primary protection — it blocks a second caller
    from registering with a *different* email (which ON CONFLICT alone
    would not catch).  ON CONFLICT DO NOTHING is a belt-and-suspenders
    guard against a narrow TOCTOU race between two simultaneous /setup
    requests.
    """
    # Primary guard: refuse if even one user exists (any email, any role).
    count = (await db.execute(select(func.count()).select_from(User))).scalar()
    if count and count > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup already complete")

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


@router.get("/signup-status")
async def signup_status(db: AsyncSession = Depends(get_db)) -> dict:
    """Open exactly when the instance has no users yet (bootstrap). Closed
    forever after — later accounts are provisioned by an admin. The retired
    signup_enabled flag no longer opens public registration."""
    count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    if count == 0:
        return {"open": True, "reason": "bootstrap"}
    return {"open": False, "reason": "closed"}


@router.get("/settings/signup", response_model=SignupSettings)
async def get_signup_settings(_: VGAdmin, db: AsyncSession = Depends(get_db)) -> SignupSettings:
    return SignupSettings(enabled=await _is_signup_enabled(db))


@router.patch("/settings/signup", response_model=SignupSettings)
async def update_signup_settings(
    body: SignupSettings, _: VGAdmin, db: AsyncSession = Depends(get_db)
) -> SignupSettings:
    setting = await db.get(AppSetting, _SIGNUP_SETTING_KEY)
    if setting is None:
        setting = AppSetting(key=_SIGNUP_SETTING_KEY, value={"enabled": body.enabled})
        db.add(setting)
    else:
        setting.value = {"enabled": body.enabled}
    await db.commit()
    log.info("signup_enabled toggled to %s", body.enabled)
    return SignupSettings(enabled=body.enabled)


@router.post("/register", response_model=UserRead, status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request,  # required by slowapi — do not remove
    body: SetupRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    """Public registration — bootstrap only.

    Creates the first vg_admin only when the instance has zero users. Once any
    user exists this endpoint always returns 409; it never mints a second
    account. All later users are created by an admin via POST /api/auth/users.
    Self-service signup was removed: it used to mint vg_admin/customer_admin
    whenever signup_enabled was on (privilege escalation risk). Equivalent to
    /setup; consolidate the two bootstrap paths in a follow-up.
    """
    count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    if count > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Registration is closed")

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
        raise HTTPException(status.HTTP_409_CONFLICT, "Registration is closed")

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
    user_id: uuid_mod.UUID, current_admin: VGAdmin, db: AsyncSession = Depends(get_db)
) -> None:
    if current_admin.id == user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Cannot delete your own account")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    await db.delete(user)
    await db.commit()
