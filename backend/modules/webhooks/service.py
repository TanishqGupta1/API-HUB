"""Webhook dispatch service â€” fire registered endpoints on push events."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import socket
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session
from .models import WebhookEndpoint

log = logging.getLogger(__name__)

SUPPORTED_EVENTS = {"push.completed", "push.failed", "push.partial_failure"}

# Max concurrent outbound webhook requests per fire_webhooks() call.
_WEBHOOK_CONCURRENCY = 8


def _sign_payload(secret: str, body: bytes) -> str:
    """Return HMAC-SHA256 hex signature for the payload."""
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _validate_webhook_url(url: str) -> str:
    """Lightweight SSRF guard â€” runs at registration time (no DNS lookup here).

    Blocks loopback/link-local by hostname string and literal private IPs.
    Full DNS resolution is deferred to _resolve_and_check() at fire time so
    the event-loop is never stalled during validation.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("https", "http"):
        raise ValueError("Webhook URL must use http or https scheme")
    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("Webhook URL must have a valid hostname")
    if hostname in ("localhost", "127.0.0.1", "::1") or hostname.startswith("169.254."):
        raise ValueError("Webhook URL must not target loopback or link-local addresses")
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_unspecified:
            raise ValueError(f"Webhook URL is a private/reserved IP ({hostname})")
    except ValueError as exc:
        if "Webhook URL" in str(exc):
            raise
        # Not a bare IP literal â€” DNS check deferred to fire time
    return url


def _resolve_and_check(hostname: str) -> None:
    """Resolve hostname â†’ IP and block private/reserved ranges (SSRF at fire time).

    Called via asyncio.to_thread so DNS resolution never blocks the event loop.
    Raises ValueError when the resolved IP is private/reserved (DNS rebinding
    protection: validates at fire time, not just at registration time).
    """
    try:
        ip_str = socket.gethostbyname(hostname)
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname: {hostname}")
    addr = ipaddress.ip_address(ip_str)
    if addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_unspecified:
        raise ValueError(
            f"Webhook target resolves to a private/reserved IP ({ip_str}) â€” "
            "SSRF protection blocked the request"
        )


async def _fire_one(
    ep: WebhookEndpoint,
    body: bytes,
    headers: dict[str, str],
    now: datetime,
) -> bool:
    """Fire a single webhook endpoint. Returns True on success.

    Resolves DNS before connecting to prevent DNS rebinding between the
    registration-time check and the actual TCP connection. Updates ep fields
    in place; caller must commit the DB session afterwards.
    """
    parsed = urlparse(ep.url)
    hostname = parsed.hostname or ""

    try:
        await asyncio.to_thread(_resolve_and_check, hostname)
    except ValueError as exc:
        log.warning("webhook %s SSRF blocked at fire time: %s", ep.id, exc)
        ep.failure_count = (ep.failure_count or 0) + 1
        ep.last_failure_at = now
        return False

    success = False
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
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
    return success


async def fire_webhooks(
    *,
    customer_id: uuid.UUID | None,
    event: str,
    payload: dict[str, Any],
) -> None:
    """Fire all active webhooks for a customer that subscribe to `event`.

    Called from execute_push after the push completes.  Never raises â€”
    failures are logged and counted but do not affect the push result.

    Uses asyncio.gather with a bounded semaphore (_WEBHOOK_CONCURRENCY) so a
    customer with many endpoints can't exhaust the connection pool or stall
    later webhooks behind a single slow endpoint.
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

        sem = asyncio.Semaphore(_WEBHOOK_CONCURRENCY)

        async def _bounded(ep: WebhookEndpoint, b: bytes, h: dict) -> None:
            async with sem:
                await _fire_one(ep, b, h, now)

        tasks = []
        for ep in endpoints:
            subscribed = set(ep.events.split(",")) if ep.events else set()
            if event not in subscribed:
                continue

            body = json.dumps({**payload, "event": event}, default=str).encode()
            fire_headers: dict[str, str] = {
                "Content-Type": "application/json",
                "X-ApiHub-Event": event,
                "X-ApiHub-Delivery": str(uuid.uuid4()),
            }
            # ep.secret is a {"value": "<raw hmac secret>"} dict decrypted by EncryptedJSON
            _raw_secret = ep.secret.get("value") if ep.secret else None
            if _raw_secret:
                fire_headers["X-ApiHub-Signature"] = f"sha256={_sign_payload(_raw_secret, body)}"

            tasks.append(_bounded(ep, body, fire_headers))

        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as exc:  # noqa: BLE001
                log.error("fire_webhooks gather error: %s", exc)

        # Single commit after all tasks complete
        await db.commit()


async def fire_test(endpoint: WebhookEndpoint) -> dict:
    """Send a test event to a webhook. Applies the same SSRF guard as fire_webhooks."""
    payload = {
        "event": "test",
        "push_log_id": "00000000-0000-0000-0000-000000000000",
        "status": "pushed",
        "ops_product_id": "12345",
        "supplier_sku": "PC61-S-Black",
        "test": True,
    }
    body = json.dumps(payload, default=str).encode()
    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-ApiHub-Event": "test",
        "X-ApiHub-Delivery": str(uuid.uuid4()),
    }
    _raw_secret = endpoint.secret.get("value") if endpoint.secret else None
    if _raw_secret:
        headers["X-ApiHub-Signature"] = f"sha256={_sign_payload(_raw_secret, body)}"

    # SSRF guard at fire time
    parsed = urlparse(endpoint.url)
    hostname = parsed.hostname or ""
    try:
        await asyncio.to_thread(_resolve_and_check, hostname)
    except ValueError as exc:
        return {"success": False, "status_code": None, "error": str(exc)}

    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
            r = await client.post(endpoint.url, content=body, headers=headers)
            return {"success": r.status_code < 300, "status_code": r.status_code, "error": None}
    except Exception as exc:
        return {"success": False, "status_code": None, "error": str(exc)}
