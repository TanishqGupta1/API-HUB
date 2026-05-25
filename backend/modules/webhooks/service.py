"""Webhook dispatch service — fire registered endpoints on push events."""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from .models import WebhookEndpoint

log = logging.getLogger(__name__)

SUPPORTED_EVENTS = {"push.completed", "push.failed", "push.partial_failure"}


def _sign_payload(secret: str, body: bytes) -> str:
    """Return HMAC-SHA256 hex signature for the payload."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


async def fire_webhooks(
    *,
    customer_id: uuid.UUID | None,
    event: str,
    payload: dict[str, Any],
) -> None:
    """Fire all active webhooks for a customer that subscribe to `event`.

    Called from execute_push after the push completes.  Never raises —
    failures are logged and counted but do not affect the push result.
    """
    if event not in SUPPORTED_EVENTS:
        return

    async with async_session() as db:
        stmt = select(WebhookEndpoint).where(
            WebhookEndpoint.is_active.is_(True),
        )
        if customer_id:
            stmt = stmt.where(
                (WebhookEndpoint.customer_id == customer_id) |
                (WebhookEndpoint.customer_id.is_(None))
            )
        else:
            stmt = stmt.where(WebhookEndpoint.customer_id.is_(None))

        endpoints = (await db.execute(stmt)).scalars().all()
        now = datetime.now(timezone.utc)

        for ep in endpoints:
            subscribed = set(ep.events.split(",")) if ep.events else set()
            if event not in subscribed:
                continue

            body = json.dumps({**payload, "event": event}, default=str).encode()
            headers = {
                "Content-Type": "application/json",
                "X-ApiHub-Event": event,
                "X-ApiHub-Delivery": str(uuid.uuid4()),
            }
            if ep.secret:
                headers["X-ApiHub-Signature"] = f"sha256={_sign_payload(ep.secret, body)}"

            success = False
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    r = await client.post(ep.url, content=body, headers=headers)
                    success = r.status_code < 300
                    if not success:
                        log.warning("webhook %s returned %s", ep.id, r.status_code)
            except Exception as exc:
                log.warning("webhook %s failed: %s", ep.id, exc)

            ep.last_fired_at = now
            if success:
                ep.failure_count = 0
            else:
                ep.failure_count = (ep.failure_count or 0) + 1
                ep.last_failure_at = now
                # Auto-disable after 10 consecutive failures
                if ep.failure_count >= 10:
                    ep.is_active = False
                    log.error(
                        "webhook %s disabled after %s consecutive failures",
                        ep.id, ep.failure_count,
                    )

        await db.commit()


async def fire_test(endpoint: WebhookEndpoint) -> dict:
    """Send a test event to a webhook. Returns result dict."""
    from datetime import datetime, timezone
    payload = {
        "event": "test",
        "push_log_id": "00000000-0000-0000-0000-000000000000",
        "status": "pushed",
        "ops_product_id": "12345",
        "supplier_sku": "PC61-S-Black",
        "test": True,
    }
    body = json.dumps(payload, default=str).encode()
    headers = {
        "Content-Type": "application/json",
        "X-ApiHub-Event": "test",
        "X-ApiHub-Delivery": str(uuid.uuid4()),
    }
    if endpoint.secret:
        headers["X-ApiHub-Signature"] = f"sha256={_sign_payload(endpoint.secret, body)}"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(endpoint.url, content=body, headers=headers)
            return {"success": r.status_code < 300, "status_code": r.status_code, "error": None}
    except Exception as exc:
        return {"success": False, "status_code": None, "error": str(exc)}
