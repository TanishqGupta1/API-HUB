import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.suppliers.models import Supplier
from .models import SyncJob
from .schemas import SyncJobCreate, SyncJobRead

router = APIRouter(prefix="/api/sync-jobs", tags=["sync_jobs"])


class SupplierSyncHealth(BaseModel):
    supplier_id: uuid.UUID
    supplier_name: str
    is_active: bool
    last_full_sync: Optional[datetime]
    last_delta_sync: Optional[datetime]
    last_sync_status: Optional[str]
    last_sync_completed_at: Optional[datetime]
    recent_error_count: int
    consecutive_failures: int


class SyncHealthResponse(BaseModel):
    suppliers: list[SupplierSyncHealth]
    generated_at: datetime


@router.get("", response_model=list[SyncJobRead])
async def list_sync_jobs(
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    supplier_id: Optional[uuid.UUID] = None,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    q = select(SyncJob).order_by(SyncJob.started_at.desc()).limit(limit)
    if status:
        q = q.where(SyncJob.status == status)
    if job_type:
        q = q.where(SyncJob.job_type == job_type)
    if supplier_id:
        q = q.where(SyncJob.supplier_id == supplier_id)
    result = await db.execute(q)
    return result.scalars().all()


@router.post("", response_model=SyncJobRead, status_code=201)
async def create_sync_job(body: SyncJobCreate, db: AsyncSession = Depends(get_db)):
    job = SyncJob(**body.model_dump(), status="pending")
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/health", response_model=SyncHealthResponse, tags=["sync_jobs"])
async def sync_health(db: AsyncSession = Depends(get_db)):
    """Per-supplier sync health: last sync times, recent error count, consecutive failures."""
    suppliers = (await db.execute(select(Supplier).order_by(Supplier.name))).scalars().all()

    result = []
    for supplier in suppliers:
        # Most recent completed job
        last_job = (
            await db.execute(
                select(SyncJob)
                .where(
                    SyncJob.supplier_id == supplier.id,
                    SyncJob.status.in_(["success", "partial_success", "completed", "failed"]),
                )
                .order_by(SyncJob.completed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()

        # Error count in last 10 jobs
        recent_jobs = (
            await db.execute(
                select(SyncJob)
                .where(SyncJob.supplier_id == supplier.id)
                .order_by(SyncJob.started_at.desc())
                .limit(10)
            )
        ).scalars().all()
        recent_error_count = sum(1 for j in recent_jobs if j.status == "failed")

        # Consecutive failures from most recent backwards
        consecutive_failures = 0
        for j in recent_jobs:
            if j.status == "failed":
                consecutive_failures += 1
            elif j.status in ("success", "partial_success", "completed"):
                break

        result.append(
            SupplierSyncHealth(
                supplier_id=supplier.id,
                supplier_name=supplier.name,
                is_active=supplier.is_active,
                last_full_sync=supplier.last_full_sync,
                last_delta_sync=supplier.last_delta_sync,
                last_sync_status=last_job.status if last_job else None,
                last_sync_completed_at=last_job.completed_at if last_job else None,
                recent_error_count=recent_error_count,
                consecutive_failures=consecutive_failures,
            )
        )

    return SyncHealthResponse(suppliers=result, generated_at=datetime.now(timezone.utc))
@router.get("/{job_id}", response_model=SyncJobRead)
async def get_sync_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(SyncJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.patch("/{job_id}", response_model=SyncJobRead)
async def update_sync_job(
    job_id: uuid.UUID,
    status: Optional[str] = None,
    records_processed: Optional[int] = None,
    error_log: Optional[str] = None,
    completed_at: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(SyncJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if status is not None:
        job.status = status
    if records_processed is not None:
        job.records_processed = records_processed
    if error_log is not None:
        job.error_log = error_log
    if completed_at is not None:
        job.completed_at = completed_at
    await db.commit()
    await db.refresh(job)
    return job
