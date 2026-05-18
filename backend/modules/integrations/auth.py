"""X-Orchestrator-Key authentication dependency for the Integration Gateway."""
import hashlib
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from .models import IntegrationKey


def _hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


async def get_orchestrator_key(
    x_orchestrator_key: Annotated[Optional[str], Header(alias="X-Orchestrator-Key")] = None,
    db: AsyncSession = Depends(get_db),
) -> IntegrationKey:
    if not x_orchestrator_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={
            "code": "BAD_SIGNATURE", "message": "X-Orchestrator-Key header required"
        })

    key_hash = _hash_key(x_orchestrator_key)
    # Filter out synthetic admin-proxy keys at SQL level — they MUST NOT
    # be reachable via the X-Orchestrator-Key header path. The admin-proxy
    # route loads them by primary key separately.
    result = await db.execute(
        select(IntegrationKey).where(
            IntegrationKey.key_hash == key_hash,
            IntegrationKey.is_synthetic == False,  # noqa: E712 — SQL boolean
        )
    )
    key = result.scalar_one_or_none()

    if not key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail={
            "code": "BAD_SIGNATURE", "message": "Invalid API key"
        })
    if key.revoked_at is not None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "KEY_REVOKED", "message": "This API key has been revoked"
        })
    if not key.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "KEY_REVOKED", "message": "This API key is inactive"
        })

    return key


def check_key_scope(
    key: IntegrationKey,
    customer_id: str,
    supplier_slug: str,
) -> None:
    if key.allowed_customer_ids and customer_id not in key.allowed_customer_ids:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "KEY_NOT_ALLOWED",
            "message": f"Key not authorized for customer {customer_id}"
        })
    if key.allowed_supplier_slugs and supplier_slug not in key.allowed_supplier_slugs:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail={
            "code": "KEY_NOT_ALLOWED",
            "message": f"Key not authorized for supplier {supplier_slug}"
        })


OrchestratorKey = Annotated[IntegrationKey, Depends(get_orchestrator_key)]
