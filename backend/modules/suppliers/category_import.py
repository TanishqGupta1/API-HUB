"""Category-driven product import for upstream suppliers.

Exposes:
- ``GET /api/suppliers/{id}/categories`` — list the supplier's category names
  for the UI picker.
- ``POST /api/suppliers/{id}/import-category`` — trigger a background import of
  N products from a named category. Returns a ``SyncJob`` the UI can poll.

For SanMar (protocol in ``soap`` / ``promostandards``) this uses the new
``PromoStandardsClient.get_categories`` + ``get_products_by_category`` methods
added in ``backend/modules/promostandards/client.py``.

Other protocols return 400 for now — extend when a category-style browse exists
for that source adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import async_session, get_db
from modules.promostandards.resolver import resolve_wsdl_url
from modules.suppliers.models import Supplier
from modules.suppliers.service import get_cached_endpoints
from modules.sync_jobs.models import SyncJob

router = APIRouter(prefix="/api/suppliers", tags=["category_import"])


# ---------------------------------------------------------------------------
# Pydantic schemas (response shapes)
# ---------------------------------------------------------------------------

class CategoryRead(BaseModel):
    name: str
    slug: str | None = None
    product_count: int | None = None
    preview_image_url: str | None = None


class ImportCategoryRequest(BaseModel):
    category_name: str = Field(min_length=1, max_length=100)
    limit: int = Field(default=10, ge=1, le=500)


class ImportCategoryResponse(BaseModel):
    job_id: UUID
    status: str
    category_name: str
    limit: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PS_PROTOCOLS = ("soap", "promostandards")


async def _load_supplier(db: AsyncSession, supplier_id: UUID) -> Supplier:
    supplier = (
        await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    ).scalar_one_or_none()
    if not supplier:
        raise HTTPException(404, "Supplier not found")
    return supplier


# ---------------------------------------------------------------------------
# Background worker
# ---------------------------------------------------------------------------

async def _run_category_import(
    job_id: UUID,
    supplier_id: UUID,
    auth_config: dict,
    wsdl_product: str,
    category_name: str,
    limit: int,
) -> None:
    """Fetch N products by category via PS SOAP and upsert into hub."""
    from modules.promostandards.client import PromoStandardsClient
    from modules.promostandards.normalizer import upsert_products

    async with async_session() as session:
        job = await session.get(SyncJob, job_id)
        if job and job.status == "queued":
            job.status = "running"
            await session.commit()

        try:
            client = PromoStandardsClient(wsdl_product, auth_config)
            products = await client.get_products_by_category(
                category_name, limit=limit
            )
            await upsert_products(
                session, supplier_id, products, inventory=None, pricing=None, media=None
            )
            job2 = await session.get(SyncJob, job_id)
            if job2:
                job2.status = "completed"
                job2.records_processed = len(products)
                job2.finished_at = datetime.now(timezone.utc)
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            job3 = await session.get(SyncJob, job_id)
            if job3:
                job3.status = "failed"
                job3.error_log = str(exc)
                job3.finished_at = datetime.now(timezone.utc)
                await session.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/{supplier_id}/categories", response_model=list[CategoryRead])
async def list_categories(
    supplier_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """List browseable categories for a supplier.

    PS/SOAP suppliers return the SanMar-style fixed category list via
    ``PromoStandardsClient.get_categories``. Other protocols return 400 until
    a category-style adapter exists for them.
    """
    supplier = await _load_supplier(db, supplier_id)

    if supplier.protocol not in PS_PROTOCOLS:
        raise HTTPException(
            400,
            f"Category browse not supported for protocol '{supplier.protocol}'. "
            "Only SOAP/PromoStandards suppliers support category listing today.",
        )

    from modules.promostandards.client import PromoStandardsClient

    endpoints = await get_cached_endpoints(db, supplier_id)
    wsdl_product = resolve_wsdl_url(endpoints, "product_data")
    # Categories method doesn't actually hit SOAP — it returns the embedded
    # SANMAR_CATEGORIES constant. But the client still needs a wsdl_url so the
    # constructor is happy. Use whatever is cached; fallback to a fake URL if
    # the supplier has no endpoints cached yet (still returns the constant).
    client = PromoStandardsClient(
        wsdl_product or "https://fake.local/ProductData?wsdl",
        dict(supplier.auth_config or {}),
    )
    categories = await client.get_categories()
    return [
        CategoryRead(
            name=c.name,
            slug=c.slug,
            product_count=c.product_count,
            preview_image_url=c.preview_image_url,
        )
        for c in categories
    ]


@router.post(
    "/{supplier_id}/import-category",
    response_model=ImportCategoryResponse,
    status_code=202,
)
async def import_category(
    supplier_id: UUID,
    body: ImportCategoryRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a background import of ``limit`` products from ``category_name``.

    Returns the SyncJob id immediately (202). Client polls
    ``GET /api/sync-jobs/{job_id}`` for progress.
    """
    supplier = await _load_supplier(db, supplier_id)

    if supplier.protocol not in PS_PROTOCOLS:
        raise HTTPException(
            400,
            f"Category import not supported for protocol '{supplier.protocol}'",
        )

    endpoints = await get_cached_endpoints(db, supplier_id)
    wsdl_product = resolve_wsdl_url(endpoints, "product_data")
    if not wsdl_product:
        raise HTTPException(
            502,
            "Product Data WSDL not found in supplier endpoint cache. "
            "Run the endpoint sync first.",
        )

    job = SyncJob(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        job_type=f"category:{body.category_name}",
        status="queued",
        started_at=datetime.now(timezone.utc),
        records_processed=0,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    background_tasks.add_task(
        _run_category_import,
        job.id,
        supplier.id,
        dict(supplier.auth_config or {}),
        wsdl_product,
        body.category_name,
        body.limit,
    )

    return ImportCategoryResponse(
        job_id=job.id,
        status=job.status,
        category_name=body.category_name,
        limit=body.limit,
    )
