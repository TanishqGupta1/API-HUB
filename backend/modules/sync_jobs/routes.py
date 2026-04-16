import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from .models import SyncJob
from .schemas import SyncJobCreate, SyncJobRead

router = APIRouter(prefix="/api/sync-jobs", tags=["sync_jobs"])


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


@router.get("/{job_id}", response_model=SyncJobRead)
async def get_sync_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(SyncJob, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/retry", response_model=SyncJobRead, status_code=201)
async def retry_sync_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    original = await db.get(SyncJob, job_id)
    if not original:
        raise HTTPException(status_code=404, detail="Job not found")
    new_job = SyncJob(
        supplier_id=original.supplier_id,
        supplier_name=original.supplier_name,
        job_type=original.job_type,
        status="pending",
        started_at=datetime.now(timezone.utc),
        records_processed=0,
    )
    db.add(new_job)
    await db.commit()
    await db.refresh(new_job)
    return new_job


@router.patch("/{job_id}", response_model=SyncJobRead)
async def update_sync_job(
    job_id: uuid.UUID,
    status: Optional[str] = None,
    records_processed: Optional[int] = None,
    error_log: Optional[str] = None,
    finished_at: Optional[datetime] = None,
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
    if finished_at is not None:
        job.finished_at = finished_at
    await db.commit()
    await db.refresh(job)
    return job
