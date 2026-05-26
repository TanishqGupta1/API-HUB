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

from database import get_db
from .models import Notification
from .schemas import NotificationRead, UnreadCount

router = APIRouter(prefix="/api/notifications", tags=["alerting"])


@router.get("", response_model=list[NotificationRead])
async def list_notifications(
    include_read: bool = False,
    db: AsyncSession = Depends(get_db),
) -> list[Notification]:
    q = select(Notification).order_by(Notification.created_at.desc())
    if not include_read:
        q = q.where(Notification.is_read == False)  # noqa: E712
    return (await db.execute(q)).scalars().all()


@router.get("/unread-count", response_model=UnreadCount)
async def unread_count(db: AsyncSession = Depends(get_db)) -> dict:
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
    db: AsyncSession = Depends(get_db),
) -> dict:
    n = await db.get(Notification, notification_id)
    if not n:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    n.is_read = True
    await db.commit()
    return {"ok": True}


@router.post("/read-all", status_code=200)
async def read_all(db: AsyncSession = Depends(get_db)) -> dict:
    await db.execute(
        update(Notification)
        .where(Notification.is_read == False)  # noqa: E712
        .values(is_read=True)
    )
    await db.commit()
    return {"ok": True}
