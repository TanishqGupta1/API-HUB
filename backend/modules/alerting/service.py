"""Alerting service — thin helper to create Notification rows."""
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .models import Notification

log = logging.getLogger("alerting")


async def create_notification(
    db: AsyncSession,
    *,
    type: str,
    severity: str,
    title: str,
    body: str,
    link: Optional[str] = None,
) -> Notification:
    """Insert a Notification row and flush (caller must commit)."""
    n = Notification(
        type=type,
        severity=severity,
        title=title,
        body=body,
        link=link,
        created_at=datetime.now(timezone.utc),
    )
    db.add(n)
    await db.flush()
    log.info("Notification created [%s] %s", type, title)
    return n
