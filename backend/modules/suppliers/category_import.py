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

import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database import async_session, get_db
from modules.promostandards.resolver import resolve_wsdl_url
from modules.suppliers.models import Supplier
from modules.suppliers.service import get_cached_endpoints
from modules.sync_jobs.models import SyncJob
from modules.promostandards.client import PromoStandardsClient
from modules.promostandards.normalizer import upsert_products, update_media_only
from modules.catalog.models import Category, Product
from modules.import_jobs.service import log as import_log

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
    fetch_images: bool = False


class ImportCategoryResponse(BaseModel):
    job_id: UUID
    status: str
    category_name: str
    limit: int


class FetchProductResponse(BaseModel):
    product_id: str
    product_name: str | None
    description: str | None
    brand: str | None
    image_url: str | None
    categories: list[str]
    variants: list[dict]


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
    wsdl_media: str | None,
    category_name: str,
    limit: int,
    extension_wsdl_url: str | None = None,
    fetch_images: bool = False,
    wsdl_pricing: str | None = None,
    wsdl_inventory: str | None = None,
) -> None:
    """Fetch N products by category via PS SOAP and upsert into hub."""
    from modules.promostandards.client import PromoStandardsClient
    from modules.promostandards.normalizer import upsert_products
    from modules.catalog.models import Category, Product
    from sqlalchemy.dialects.postgresql import insert as pg_insert
    from sqlalchemy import update
    import re

    async with async_session() as session:
        job = await session.get(SyncJob, job_id)
        if job and job.status == "queued":
            job.status = "running"
            await session.commit()

        try:
            client = PromoStandardsClient(wsdl_product, auth_config)
            products = await client.get_products_by_category(
                category_name,
                limit=limit,
                extension_wsdl_url=extension_wsdl_url,
            )

            if job:
                job.total_products = len(products)
                await session.commit()
                await session.refresh(job)

            if not products:
                # Still finalize if no products found
                if job:
                    job.status = "completed"
                    job.completed_at = datetime.now(timezone.utc)
                    await session.commit()
                return

            cat_slug = re.sub(r"[^a-z0-9]+", "-", category_name.lower()).strip("-")

            # Ensure category exists — use external_id key for idempotency
            cat_res = await session.execute(
                select(Category).where(
                    Category.supplier_id == supplier_id,
                    Category.external_id == cat_slug
                )
            )
            db_cat = cat_res.scalar_one_or_none()
            if not db_cat:
                db_cat = Category(
                    supplier_id=supplier_id,
                    name=category_name,
                    external_id=cat_slug,
                )
                session.add(db_cat)
                await session.flush()

            # 1. Fetch pricing and inventory in parallel before upserting
            product_ids = [p.product_id for p in products]

            pricing_data = None
            inventory_data = None

            if wsdl_pricing:
                try:
                    if job:
                        job.error_log = f"Fetching pricing for {len(product_ids)} products..."
                        await session.commit()
                    pricing_client = PromoStandardsClient(wsdl_pricing, auth_config)
                    pricing_data = await pricing_client.get_pricing(product_ids)
                except Exception as exc:  # noqa: BLE001
                    import_log.warning("Pricing fetch failed: %s", exc)

            if wsdl_inventory:
                try:
                    if job:
                        job.error_log = f"Fetching inventory for {len(product_ids)} products..."
                        await session.commit()
                    inventory_client = PromoStandardsClient(wsdl_inventory, auth_config)
                    inventory_data = await inventory_client.get_inventory(product_ids)
                except Exception as exc:  # noqa: BLE001
                    import_log.warning("Inventory fetch failed: %s", exc)

            if job:
                job.error_log = None
                await session.commit()

            # 2. Save products with pricing and inventory
            await upsert_products(
                session,
                supplier_id,
                products,
                inventory=inventory_data,
                pricing=pricing_data,
                media=None,
                category_id=db_cat.id
            )
            
            if job:
                job.records_processed = len(products)
                await session.commit()
                await session.refresh(job)

            # 3. Enrich images if requested.
            #
            # PERF: `PromoStandardsClient.get_media` already has an internal
            # semaphore that runs up to 5 SOAP calls in parallel. The old
            # code called it once per product in a serial for-loop, which
            # collapsed the concurrency down to 1 (each call had a
            # single-element list, so there was only one task to schedule).
            # For 21 products at ~10s/call, that was ~210s — most of the
            # 7-minute import. Batching all product_ids into one call lets
            # the semaphore actually parallelize: ~ceil(N/5) × per-call
            # latency, so 21 products drops to ~5 rounds ≈ 50s.
            if fetch_images and wsdl_media and products:
                media_client = PromoStandardsClient(wsdl_media, auth_config)
                all_pids = [p.product_id for p in products]
                if job:
                    job.error_log = (
                        f"Enriching media for {len(all_pids)} products "
                        f"(up to 5 in parallel)..."
                    )
                    await session.commit()
                try:
                    media_items = await media_client.get_media(all_pids)
                    if media_items:
                        await update_media_only(session, supplier_id, media_items)
                except Exception as e:  # noqa: BLE001
                    import_log.warning(
                        "Batch media enrichment failed for %d products: %s",
                        len(all_pids), e,
                    )
                finally:
                    # Clear the in-flight status so the next status check
                    # (and the final UI render) doesn't keep showing
                    # "Enriching media..." after this phase completes.
                    if job:
                        job.error_log = None
                        await session.commit()

            # Upsert a Category row for this category_name so the sidebar shows it
            if products:
                stmt = pg_insert(Category).values(
                    supplier_id=supplier_id,
                    external_id=cat_slug,
                    name=category_name,
                    sort_order=0,
                ).on_conflict_do_update(
                    index_elements=["supplier_id", "external_id"],
                    set_={"name": category_name},
                )
                result = await session.execute(stmt.returning(Category.id))
                category_id = result.scalar_one()

                # Link imported products to this category
                product_skus = [p.product_id for p in products]
                await session.execute(
                    update(Product)
                    .where(
                        Product.supplier_id == supplier_id,
                        Product.supplier_sku.in_(product_skus),
                    )
                    .values(category_id=category_id)
                )
                await session.commit()

            job2 = await session.get(SyncJob, job_id)
            if job2:
                job2.status = "completed"
                job2.error_log = None # Clear the status message
                job2.completed_at = datetime.now(timezone.utc)
                await session.commit()
        except Exception as exc:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            if job:
                job.status = "failed"
                job.error_log = str(exc)
                job.completed_at = datetime.now(timezone.utc)
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
    wsdl_media = resolve_wsdl_url(endpoints, "media_content") if body.fetch_images else None
    wsdl_pricing = resolve_wsdl_url(endpoints, "ppc")
    wsdl_inventory = resolve_wsdl_url(endpoints, "inventory")

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

    # SanMar's getProductInfoByCategory is a non-PS extension, not on the
    # ProductData binding. Route via SANMAR_EXT_WSDL when the supplier is
    # SanMar. Other PS suppliers fail fast with an empty result + warning log.
    from modules.promostandards.client import SANMAR_EXT_WSDL

    extension_wsdl_url: str | None = None
    if (supplier.promostandards_code or "").upper() == "SANMAR":
        extension_wsdl_url = SANMAR_EXT_WSDL

    background_tasks.add_task(
        _run_category_import,
        job.id,
        supplier.id,
        dict(supplier.auth_config or {}),
        wsdl_product,
        wsdl_media,
        body.category_name,
        body.limit,
        extension_wsdl_url,
        body.fetch_images,
        wsdl_pricing,
        wsdl_inventory,
    )

    return ImportCategoryResponse(
        job_id=job.id,
        status=job.status,
        category_name=body.category_name,
        limit=body.limit,
    )


@router.get("/{supplier_id}/fetch-product", response_model=FetchProductResponse)
async def fetch_single_product(
    supplier_id: UUID,
    style_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a single product by Style ID (SKU) for preview.
    
    This is a synchronous-feeling call (awaits the SOAP response) used for
    UI previews before a full import.
    """
    supplier = await _load_supplier(db, supplier_id)

    if supplier.protocol not in PS_PROTOCOLS:
        raise HTTPException(
            400, f"Fetch-product not supported for protocol '{supplier.protocol}'"
        )

    from modules.promostandards.client import PromoStandardsClient
    from modules.promostandards.resolver import resolve_wsdl_url

    endpoints = await get_cached_endpoints(db, supplier_id)
    wsdl_product = resolve_wsdl_url(endpoints, "product_data")
    if not wsdl_product:
        raise HTTPException(
            502, "Product Data WSDL not found in supplier endpoint cache."
        )

    client = PromoStandardsClient(wsdl_product, dict(supplier.auth_config or {}))
    product = await client.get_product(style_id)
    
    if not product:
        raise HTTPException(404, f"Product '{style_id}' not found at supplier.")

    return FetchProductResponse(
        product_id=product.product_id,
        product_name=product.product_name,
        description=product.description,
        brand=product.brand,
        image_url=product.primary_image_url,
        categories=product.categories,
        variants=[
            {
                "color": v.color_name,
                "size": v.size_name,
                "part_id": v.part_id,
            }
            for v in product.parts
        ],
    )


@router.post("/{supplier_id}/import-product", status_code=201)
async def import_single_product(
    supplier_id: UUID,
    style_id: str = Query(..., min_length=1),
    db: AsyncSession = Depends(get_db),
):
    """Fetch and immediately import a single product into the catalog."""
    supplier = await _load_supplier(db, supplier_id)

    if supplier.protocol not in PS_PROTOCOLS:
        raise HTTPException(
            400, f"Import-product not supported for protocol '{supplier.protocol}'"
        )

    from modules.promostandards.client import PromoStandardsClient
    from modules.promostandards.resolver import resolve_wsdl_url
    from modules.promostandards.normalizer import upsert_products

    endpoints = await get_cached_endpoints(db, supplier_id)
    wsdl_product = resolve_wsdl_url(endpoints, "product_data")
    if not wsdl_product:
        raise HTTPException(
            502, "Product Data WSDL not found in supplier endpoint cache."
        )

    client = PromoStandardsClient(wsdl_product, dict(supplier.auth_config or {}))
    product = await client.get_product(style_id)
    
    if not product:
        raise HTTPException(404, f"Product '{style_id}' not found at supplier.")

    await upsert_products(db, supplier_id, [product], inventory=None, pricing=None, media=None)
    await db.commit()
    
    return {"success": True, "product_id": product.product_id}
