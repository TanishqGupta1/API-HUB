import hmac
import os
import uuid as uuid_mod
from typing import Annotated

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

from .models import User
from .security import decode_token


# A sentinel "service" user returned for trusted service-to-service calls
# authenticated via X-Ingest-Secret (e.g. n8n → FastAPI). It is never persisted.
_SERVICE_ACCOUNT_ID = uuid_mod.UUID("00000000-0000-0000-0000-000000000001")

# X-Ingest-Secret only authorizes calls under these path prefixes. Anything
# else (admin user management, audit logs, OPS-customer config, etc.) still
# requires a JWT cookie. Narrows blast radius if the shared secret leaks.
#
# Security model (two layers):
#   1. Path allowlist below — keeps the ingest secret away from sensitive
#      admin routes (/api/auth, /api/customers, /api/audit-log, etc.).
#   2. Role = "ingest_service" (not "vg_admin") — VGAdmin-gated routes
#      reject this caller even if the secret leaks to an allowed path.
#
# Why /api/sync/* is listed broadly (not per-supplier):
#   n8n calls /api/sync/{supplier_id}/products|inventory|pricing for every
#   supplier. Locking to a single slug would require a new allowlist entry
#   per supplier, breaking the adapter-pattern design. The role restriction
#   above is the real guard; the path list is a coarse first filter.
_INGEST_ALLOWED_PATH_PREFIXES: tuple[str, ...] = (
    "/api/ingest",
    "/api/sync",
    "/api/sync-jobs",
    "/api/suppliers",
    "/api/push-log",
    "/api/push-mappings",
    "/api/push-candidates",
    "/api/ops-options",
    "/api/catalog",
    "/api/products",
    "/api/markup",
    "/health",
)


def _service_account_user() -> User:
    """Synthetic user for trusted n8n service calls.

    Role is `ingest_service` (NOT `vg_admin`) so VGAdmin-gated routes —
    user CRUD, audit log access, etc. — refuse this caller even if the
    INGEST_SHARED_SECRET leaks.
    """
    user = User()
    user.id = _SERVICE_ACCOUNT_ID
    user.email = "n8n@service.local"
    user.hashed_password = ""
    user.role = "ingest_service"
    user.customer_id = None
    user.is_active = True
    return user


def _ingest_secret_matches(provided: str | None) -> bool:
    expected = os.getenv("INGEST_SHARED_SECRET", "").strip()
    if not expected or provided is None:
        return False
    return hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8"))


def _path_allowed_for_service(path: str) -> bool:
    return any(path == p or path.startswith(p + "/") for p in _INGEST_ALLOWED_PATH_PREFIXES)


async def get_current_user(
    request: Request,
    auth_token: Annotated[str | None, Cookie(alias="auth_token")] = None,
    x_ingest_secret: Annotated[str | None, Header(alias="X-Ingest-Secret")] = None,
    db: AsyncSession = Depends(get_db),
) -> User:
    # Service-to-service path: trusted n8n container calls send X-Ingest-Secret.
    # Accepted only on the ingest path allow-list; bypasses JWT for those routes.
    if _ingest_secret_matches(x_ingest_secret):
        if not _path_allowed_for_service(request.url.path):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Service token not authorized for this path",
            )
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


def _require_customer_admin(current_user: CurrentUser) -> User:
    if current_user.role != "customer_admin" or current_user.customer_id is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customer admin access required")
    return current_user


def _require_any_admin(current_user: CurrentUser) -> User:
    if current_user.role not in ("vg_admin", "customer_admin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    return current_user


VGAdmin = Annotated[User, Depends(_require_vg_admin)]
CustomerAdmin = Annotated[User, Depends(_require_customer_admin)]
AnyAdmin = Annotated[User, Depends(_require_any_admin)]


def require_customer_access(
    customer_id: uuid_mod.UUID,
    current_user: CurrentUser,
) -> uuid_mod.UUID:
    """Authorize access to one customer's data. Use as a route dependency on
    any path with a ``customer_id`` path param.

    vg_admin and the trusted ingest service may act on any customer;
    customer_admin only on their own; everyone else is forbidden.
    """
    if current_user.role in ("vg_admin", "ingest_service"):
        return customer_id
    if current_user.role == "customer_admin" and current_user.customer_id == customer_id:
        return customer_id
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this customer")
