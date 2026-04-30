"""Manual import endpoint. Returns 202 + sync_job_id; work runs in background."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.suppliers.models import Supplier

from .schemas import ImportRequest, ImportResponse
from .service import create_pending_import_job, run_existing_import_job


router = APIRouter(prefix="/api/suppliers", tags=["import_jobs"])


@router.post("/{supplier_id}/import", response_model=ImportResponse, status_code=202)
async def trigger_import(
    supplier_id: uuid.UUID,
    body: ImportRequest,
    background: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
) -> ImportResponse:
    supplier = await db.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(404, f"supplier {supplier_id} not found")
    if not supplier.adapter_class:
        raise HTTPException(
            409,
            f"supplier {supplier.name!r} has no adapter_class set; "
            f"configure one before importing",
        )

    from sqlalchemy import select
    from modules.sync_jobs.models import SyncJob

    in_flight = (await db.execute(
        select(SyncJob.id).where(
            SyncJob.supplier_id == supplier_id,
            SyncJob.job_type == f"import:{body.mode.value}",
            SyncJob.status.in_(("queued", "running")),
        ).limit(1)
    )).scalar_one_or_none()
    if in_flight is not None:
        raise HTTPException(
            409,
            f"import already running for supplier {supplier.name!r} mode {body.mode.value!r} (job {in_flight})",
        )

    job_id = await create_pending_import_job(supplier_id=supplier_id, mode=body.mode)

    background.add_task(
        run_existing_import_job,
        job_id=job_id,
        supplier_id=supplier_id,
        mode=body.mode,
        limit=body.limit,
        explicit_list=body.explicit_list,
    )

    return ImportResponse(
        sync_job_id=job_id,
        supplier_id=supplier_id,
        mode=body.mode,
        accepted_at=datetime.now(timezone.utc).isoformat(),
    )
