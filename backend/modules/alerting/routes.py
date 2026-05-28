"""Alerting API routes.

GET  /api/notifications              — list unread (or all with ?include_read=true)
GET  /api/notifications/unread-count — lightweight badge count poll
PATCH /api/notifications/{id}/read  — dismiss one
POST /api/notifications/read-all    — dismiss all
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, ENVIRONMENT
from modules.auth.dependencies import VGAdmin
from .models import Notification
from .schemas import NotificationRead, UnreadCount

router = APIRouter(prefix="/api/notifications", tags=["alerting"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    include_read: bool = False,
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
) -> list[Notification]:
    q = select(Notification).order_by(Notification.created_at.desc())
    if not include_read:
        q = q.where(Notification.is_read == False)  # noqa: E712
    return (await db.execute(q)).scalars().all()


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    count = (
        await db.execute(
            select(func.count(Notification.id)).where(
                Notification.is_read == False  # noqa: E712
            )
        )
    ).scalar_one()
    return {"count": count}


@router.patch("/{notification_id}/read", status_code=200)
async def mark_read(
    notification_id: UUID,
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    n = await db.get(Notification, notification_id)
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    n.is_read = True
    await db.commit()
    return {"ok": True}


@router.post("/read-all", status_code=200)
async def read_all(
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    await db.execute(
        update(Notification)
        .where(Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}


@router.post("/demo", status_code=201)
async def create_demo_notifications(
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create one sample notification of each type so the UI can be demoed
    without waiting for a real failure. Non-production only."""
    if ENVIRONMENT == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Demo endpoint is not available in production.",
        )
    from .service import create_notification

    await create_notification(
        db,
        type="push_failed",
        severity="error",
        title="Push failed — PC61 for full_catalog_push",
        body=(
            "Customer: full_catalog_push\n"
            "Error: OPS returned HTTP 500 — internal server error\n"
            "Time: just now"
        ),
        link="/push-log",
    )
    await create_notification(
        db,
        type="sync_failed",
        severity="error",
        title="Sync failed — SanMar (inventory)",
        body=(
            "Records processed: 8412\n"
            "Failed: 23\n"
            "Error: SOAP fault: Authentication token expired\n"
            "Started: just now"
        ),
        link="/sync",
    )
    await create_notification(
        db,
        type="scheduler_down",
        severity="warning",
        title="Scheduler may be down",
        body=(
            "Last successful run was 3.2 hour(s) ago.\n"
            "Expected every 1 hour(s).\n"
            "If DISABLE_SCHEDULER=true this alert can be ignored."
        ),
        link="/monitoring",
    )
    await db.commit()
    return {"created": 3}
