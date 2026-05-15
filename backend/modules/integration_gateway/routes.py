"""Integration Gateway routes — `/api/integrations/v1/*`. T16 only so far."""
from __future__ import annotations

import uuid as uuid_mod
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.push_log.models import ProductPushLog

from modules.integrations.schemas import (
    PushRequestLinks,
    PushStatusOut,
    StepResultOut,
)

from .auth import OrchestratorContext, require_orchestrator_key

router = APIRouter(prefix="/api/integrations/v1", tags=["integration_gateway"])


@router.get(
    "/push-requests/{push_log_id}",
    response_model=PushStatusOut,
    summary="Poll a push request's current status",
)
async def get_push_request(
    push_log_id: uuid_mod.UUID,
    ctx: Annotated[OrchestratorContext, Depends(require_orchestrator_key)],
    db: AsyncSession = Depends(get_db),
) -> PushStatusOut:
    """Status poll. `finished_at` set on terminal states; null while in-flight."""
    row = await db.get(ProductPushLog, push_log_id)
    if not row:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail={"code": "UNKNOWN_REF", "message": "Push request not found"},
        )

    terminal = row.status in {
        "pushed",
        "failed",
        "partial_failure",
        "rejected",
        "canceled",
        "dry_run_pushed",
    }

    return PushStatusOut(
        push_log_id=row.id,
        status=row.status,
        customer_id=row.customer_id,
        supplier_slug=row.supplier_slug,
        supplier_sku=row.supplier_sku,
        ops_product_id=row.ops_product_id,
        error=row.error,
        step_results=(
            [StepResultOut(**s) for s in row.step_results]
            if row.step_results
            else None
        ),
        cleanup_targets=row.cleanup_targets,
        callback_status=row.callback_status or "not_requested",
        callback_attempts=row.callback_attempts or 0,
        finished_at=row.pushed_at if terminal else None,
        links=PushRequestLinks(
            self=f"/api/integrations/v1/push-requests/{push_log_id}"
        ),
    )
