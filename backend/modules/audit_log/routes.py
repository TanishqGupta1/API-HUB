from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import VGAdmin

from .models import AuditLog

router = APIRouter(prefix="/api/audit-log", tags=["audit_log"])


class AuditLogRead(BaseModel):
    id: UUID
    user_email: Optional[str]
    user_id: Optional[str]
    method: str
    path: str
    status_code: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[AuditLogRead], dependencies=[Depends(VGAdmin)])
async def list_audit_logs(
    limit: int = Query(default=100, le=500),
    user_email: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog).order_by(AuditLog.created_at.desc())
    if user_email:
        q = q.where(AuditLog.user_email == user_email)
    q = q.limit(limit)
    rows = (await db.execute(q)).scalars().all()
    return rows
