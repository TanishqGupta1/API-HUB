"""Webhook endpoint CRUD + test-fire routes."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import AnyAdmin
from modules.auth.models import User

from .models import WebhookEndpoint
from .schemas import WebhookCreate, WebhookRead, WebhookTestResult
from .service import _validate_webhook_url, fire_test

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


class WebhookUpdate(BaseModel):
    url: Optional[str] = None
    events: Optional[list[str]] = None
    secret: Optional[str] = None
    is_active: Optional[bool] = None


_ALLOWED_EVENTS = {"push.completed", "push.failed", "push.partial_failure"}


def _check_ownership(ep: WebhookEndpoint, user: User) -> None:
    """Raise 403 if a customer_admin tries to touch another customer's webhook."""
    if user.role == "vg_admin":
        return
    if ep.customer_id != user.customer_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Access denied")


@router.get("", response_model=list[WebhookRead])
async def list_webhooks(
    user: AnyAdmin,
    db: AsyncSession = Depends(get_db),
) -> list[WebhookRead]:
    stmt = select(WebhookEndpoint).order_by(WebhookEndpoint.created_at.desc())
    if user.role != "vg_admin":
        stmt = stmt.where(WebhookEndpoint.customer_id == user.customer_id)
    endpoints = (await db.execute(stmt)).scalars().all()
    return [WebhookRead.from_model(ep) for ep in endpoints]


@router.post("", response_model=WebhookRead, status_code=201)
async def create_webhook(
    body: WebhookCreate,
    user: AnyAdmin,
    db: AsyncSession = Depends(get_db),
) -> WebhookRead:
    # customer_admin may only create webhooks scoped to their own customer
    customer_id = body.customer_id
    if user.role != "vg_admin":
        customer_id = user.customer_id

    ep = WebhookEndpoint(
        customer_id=customer_id,
        url=body.url,
        events=",".join(body.events),
        # Store secret as {"value": raw_secret} dict for EncryptedJSON (impl=Text, Fernet-encrypted)
        secret={"value": body.secret} if body.secret else None,
        is_active=True,
        failure_count=0,
    )
    db.add(ep)
    await db.commit()
    await db.refresh(ep)
    return WebhookRead.from_model(ep)


@router.get("/{endpoint_id}", response_model=WebhookRead)
async def get_webhook(
    endpoint_id: uuid.UUID,
    user: AnyAdmin,
    db: AsyncSession = Depends(get_db),
) -> WebhookRead:
    ep = await db.get(WebhookEndpoint, endpoint_id)
    if not ep:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    _check_ownership(ep, user)
    return WebhookRead.from_model(ep)


@router.patch("/{endpoint_id}", response_model=WebhookRead)
async def update_webhook(
    endpoint_id: uuid.UUID,
    body: WebhookUpdate,
    user: AnyAdmin,
    db: AsyncSession = Depends(get_db),
) -> WebhookRead:
    ep = await db.get(WebhookEndpoint, endpoint_id)
    if not ep:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    _check_ownership(ep, user)

    if body.url is not None:
        try:
            _validate_webhook_url(body.url)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
        ep.url = body.url

    if body.events is not None:
        invalid = set(body.events) - _ALLOWED_EVENTS
        if invalid:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                f"Unknown events: {invalid}. Allowed: {_ALLOWED_EVENTS}",
            )
        ep.events = ",".join(body.events)

    if body.secret is not None:
        # Empty string clears the secret; non-empty stored as {"value": raw} for EncryptedJSON
        ep.secret = {"value": body.secret} if body.secret else None

    if body.is_active is not None:
        ep.is_active = body.is_active
        if body.is_active:
            # Re-enabling resets the failure counter
            ep.failure_count = 0

    await db.commit()
    await db.refresh(ep)
    return WebhookRead.from_model(ep)


@router.delete("/{endpoint_id}", status_code=204)
async def delete_webhook(
    endpoint_id: uuid.UUID,
    user: AnyAdmin,
    db: AsyncSession = Depends(get_db),
) -> None:
    ep = await db.get(WebhookEndpoint, endpoint_id)
    if not ep:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    _check_ownership(ep, user)
    await db.delete(ep)
    await db.commit()


@router.post("/{endpoint_id}/test", response_model=WebhookTestResult)
async def test_webhook(
    endpoint_id: uuid.UUID,
    user: AnyAdmin,
    db: AsyncSession = Depends(get_db),
) -> WebhookTestResult:
    ep = await db.get(WebhookEndpoint, endpoint_id)
    if not ep:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Webhook not found")
    _check_ownership(ep, user)

    result = await fire_test(ep)
    return WebhookTestResult(
        success=result["success"],
        status_code=result["status_code"],
        error=result["error"],
        fired_at=datetime.now(timezone.utc),
    )
