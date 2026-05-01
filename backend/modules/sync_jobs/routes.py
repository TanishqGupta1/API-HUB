import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select, text
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
    """Per-supplier sync health. Uses 2 queries total instead of N+1."""
    suppliers = (await db.execute(select(Supplier).order_by(Supplier.name))).scalars().all()
    if not suppliers:
        return SyncHealthResponse(suppliers=[], generated_at=datetime.now(timezone.utc))

    supplier_ids = [s.id for s in suppliers]

    # Query 1: last terminal job per supplier (window function)
    last_job_rows = (await db.execute(
        text("""
            SELECT DISTINCT ON (supplier_id)
                supplier_id, status, completed_at
            FROM sync_jobs
            WHERE supplier_id = ANY(:ids)
              AND status IN ('success', 'partial_success', 'completed', 'failed')
            ORDER BY supplier_id, completed_at DESC NULLS LAST
        """),
        {"ids": supplier_ids},
    )).mappings().all()
    last_job_by_supplier = {r["supplier_id"]: r for r in last_job_rows}

    # Query 2: last 10 jobs per supplier for error counting
    recent_rows = (await db.execute(
        text("""
            SELECT supplier_id, status, row_num
            FROM (
                SELECT supplier_id, status,
                       ROW_NUMBER() OVER (PARTITION BY supplier_id ORDER BY started_at DESC) AS row_num
                FROM sync_jobs
                WHERE supplier_id = ANY(:ids)
            ) ranked
            WHERE row_num <= 10
        """),
        {"ids": supplier_ids},
    )).mappings().all()

    from collections import defaultdict
    recent_by_supplier: dict = defaultdict(list)
    for r in recent_rows:
        recent_by_supplier[r["supplier_id"]].append(r["status"])

    result = []
    for supplier in suppliers:
        last = last_job_by_supplier.get(supplier.id)
        recent_statuses = recent_by_supplier.get(supplier.id, [])
        recent_error_count = sum(1 for s in recent_statuses if s == "failed")
        consecutive_failures = 0
        for s in recent_statuses:
            if s == "failed":
                consecutive_failures += 1
            elif s in ("success", "partial_success", "completed"):
                break

        result.append(SupplierSyncHealth(
            supplier_id=supplier.id,
            supplier_name=supplier.name,
            is_active=supplier.is_active,
            last_full_sync=supplier.last_full_sync,
            last_delta_sync=supplier.last_delta_sync,
            last_sync_status=last["status"] if last else None,
            last_sync_completed_at=last["completed_at"] if last else None,
            recent_error_count=recent_error_count,
            consecutive_failures=consecutive_failures,
        ))

    return SyncHealthResponse(suppliers=result, generated_at=datetime.now(timezone.utc))


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
