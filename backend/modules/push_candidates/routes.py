from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

from .service import list_candidates

router = APIRouter(prefix="/api/push", tags=["push_candidates"])


@router.get("/candidates/{customer_id}")
async def get_push_candidates(
    customer_id: UUID,
    supplier_id: Optional[UUID] = Query(None),
    only_never_pushed: bool = Query(False),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db),
):
    return await list_candidates(db, customer_id, supplier_id, only_never_pushed, limit)
