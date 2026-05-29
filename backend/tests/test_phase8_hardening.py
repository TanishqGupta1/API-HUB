"""Phase 8 admin UX hardening tests.

Covers the medium review items from PR #137 round 2:
- Batch-push exception isolation: per-customer exception → error item, not 500
- Master-options sync bad UUID query param → 422 (FastAPI validation)
- auth/refresh malformed sub → 401 (not 500, guards UUID parse regression)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from jose import jwt


# ---------------------------------------------------------------------------
# Batch-push: per-customer exception → error item, not 500
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_batch_push_generic_exception_becomes_error_item(client):
    """Per-customer RuntimeError must be caught and returned as status='error'.

    The batch-push handler wraps each customer in try/except to isolate
    failures. This test asserts that a generic internal error surfaces as
    a generic message — not a 500, and not leaking the exception text.
    """
    cid = str(uuid4())
    with (
        patch(
            "modules.integrations.routes.get_or_create_admin_proxy_key",
            new=AsyncMock(return_value="proxy-key"),
        ),
        patch(
            "modules.integrations.routes.prepare_push_intent",
            new=AsyncMock(side_effect=RuntimeError("DB exploded")),
        ),
    ):
        resp = await client.post(
            "/api/integrations/admin/batch-push-requests",
            json={
                "product_id": str(uuid4()),
                "supplier_slug": "test-slug",
                "customer_ids": [cid],
                "dry_run": False,
            },
        )

    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["status"] == "error"
    assert item["push_log_id"] is None
    # Generic exception must NOT leak the internal message
    assert item["error"] == "Push acceptance failed"
    assert "DB exploded" not in (item["error"] or "")


@pytest.mark.asyncio
async def test_batch_push_http_exception_detail_surfaced(client):
    """HTTPException.detail (up to 200 chars) must be forwarded as the error field."""
    from fastapi import HTTPException, status as http_status

    cid = str(uuid4())
    with (
        patch(
            "modules.integrations.routes.get_or_create_admin_proxy_key",
            new=AsyncMock(return_value="proxy-key"),
        ),
        patch(
            "modules.integrations.routes.prepare_push_intent",
            new=AsyncMock(
                side_effect=HTTPException(
                    http_status.HTTP_422_UNPROCESSABLE_ENTITY, "Product not ready"
                )
            ),
        ),
    ):
        resp = await client.post(
            "/api/integrations/admin/batch-push-requests",
            json={
                "product_id": str(uuid4()),
                "supplier_slug": "test-slug",
                "customer_ids": [cid],
                "dry_run": False,
            },
        )

    assert resp.status_code == 202, resp.text
    item = resp.json()["items"][0]
    assert item["status"] == "error"
    assert "Product not ready" in item["error"]


# ---------------------------------------------------------------------------
# master-options sync: invalid UUID query param → 422
# ---------------------------------------------------------------------------


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_master_options_sync_bad_uuid_returns_422(client):
    """?customer_id= with a non-UUID value must return 422 (FastAPI validation).

    Guards against uuid.UUID() raising ValueError inside the handler (which
    would produce a 500) — FastAPI should catch it before the handler runs.
    """
    resp = await client.post("/api/master-options/sync?customer_id=not-a-uuid")
    assert resp.status_code == 422, resp.text


# ---------------------------------------------------------------------------
# auth/refresh: malformed sub → 401 not 500
# ---------------------------------------------------------------------------


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_refresh_malformed_sub_returns_401(client):
    """Refresh token with non-UUID sub must yield 401, not 500.

    Without the UUID parse guard, ``uuid.UUID(claims["sub"])`` raises
    ValueError which would propagate as an unhandled 500.
    """
    from modules.auth.security import ALGORITHM, JWT_SECRET_KEY

    bad_token = jwt.encode(
        {
            "sub": "not-a-valid-uuid",
            "type": "refresh",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        JWT_SECRET_KEY,
        algorithm=ALGORITHM,
    )
    resp = await client.post(
        "/api/auth/refresh",
        cookies={"refresh_token": bad_token},
    )
    assert resp.status_code == 401, resp.text
