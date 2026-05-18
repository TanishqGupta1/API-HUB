"""Synthetic IntegrationKey for the admin-UI push proxy.

The admin UI authenticates with a JWT, not an X-Orchestrator-Key header, but
the push pipeline (`prepare_push_intent` / `execute_push`) requires an
IntegrationKey so it can stamp `push_log.key_id` for audit + tie idempotency
records to a key.

Solution: persist a synthetic key row with `is_synthetic=True`. The header
auth path (`get_orchestrator_key`) filters `is_synthetic == False` at SQL
level, so this key cannot be forged via X-Orchestrator-Key. Loaded by
primary key only from the JWT-authed admin route.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from .models import IntegrationKey

ADMIN_PROXY_KEY_ID = "_admin_ui_proxy"


async def get_or_create_admin_proxy_key(db: AsyncSession) -> IntegrationKey:
    """Idempotent singleton for the synthetic admin-proxy IntegrationKey."""
    key = await db.get(IntegrationKey, ADMIN_PROXY_KEY_ID)
    if key:
        return key
    key = IntegrationKey(
        id=ADMIN_PROXY_KEY_ID,
        key_hash="synthetic-no-header-lookup",
        name="Admin UI proxy (JWT-authenticated)",
        allowed_customer_ids=None,
        allowed_supplier_slugs=None,
        rate_limit_per_minute=600,
        is_synthetic=True,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key
