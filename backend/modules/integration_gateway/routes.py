"""Integration Gateway routes — `/api/integrations/v1/*`.

The plan lays out 5 endpoints in this file:
  T15  POST /push-requests              (Urvashi)
  T16  GET  /push-requests/{push_log_id}  ← THIS task
  T17  POST /suppliers/{slug}/products   (Urvashi)
  T18  POST /master-options/ingest + others (Urvashi)

For now only T16's GET is wired. The router prefix matches the spec.
"""
from __future__ import annotations

import uuid as uuid_mod
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.push_log.models import ProductPushLog

# Bridge-import from Vidhi's existing schemas until T14 lands the
# integration_gateway-native versions. Same wire shape, same field names.
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
    """Return the current state of a push request.

    Terminal states (`pushed`, `failed`, `partial_failure`, `rejected`,
    `canceled`, `dry_run_pushed`) include `finished_at`. In-flight states
    (`accepted`, `queued`, `processing`) leave it null so clients can keep
    polling.
    """
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
