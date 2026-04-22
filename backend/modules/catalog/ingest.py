"""Write-side (n8n-facing) catalog endpoints.

Each endpoint requires the X-Ingest-Secret header and writes a SyncJob
row describing the batch. Upserts are idempotent via ON CONFLICT DO
UPDATE — re-running a workflow is safe.

The four endpoints share one normalized contract shape (see schemas.py)
so every supplier protocol (SanMar SOAP, S&S REST, 4Over HMAC, VG OPS
GraphQL) feeds the same payload format.
"""
import os
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.suppliers.models import Supplier
from modules.sync_jobs.models import SyncJob

from .models import (
    Category,
    Product,
    ProductImage,
    ProductOption,
    ProductOptionAttribute,
    ProductVariant,
)
from .schemas import (
    CategoryIngest,
    IngestResult,
    InventoryIngest,
    OptionIngest,
    PriceIngest,
    ProductIngest,
)

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


# ---------------------------------------------------------------------------
# Auth + helpers
# ---------------------------------------------------------------------------

def _expected_secret() -> str:
    value = os.getenv("INGEST_SHARED_SECRET")
    if not value:
        raise HTTPException(500, "INGEST_SHARED_SECRET not configured")
    return value


async def require_ingest_secret(x_ingest_secret: str | None = Header(default=None)) -> None:
    if x_ingest_secret != _expected_secret():
        raise HTTPException(401, "Invalid or missing X-Ingest-Secret header")


async def _load_active_supplier(supplier_id: UUID, db: AsyncSession) -> Supplier:
    supplier = await db.get(Supplier, supplier_id)
    if not supplier:
        raise HTTPException(404, f"Supplier {supplier_id} not found")
    if not supplier.is_active:
        raise HTTPException(409, f"Supplier '{supplier.name}' is not active")
    return supplier


async def _start_sync_job(db: AsyncSession, supplier: Supplier, job_type: str) -> SyncJob:
    job = SyncJob(
        supplier_id=supplier.id,
        supplier_name=supplier.name,
        job_type=job_type,
        status="running",
        started_at=datetime.now(timezone.utc),
        records_processed=0,
    )
    db.add(job)
    await db.flush()
    return job


async def _finish_sync_job(db: AsyncSession, job: SyncJob, records: int) -> None:
    job.status = "completed"
    job.records_processed = records
    job.finished_at = datetime.now(timezone.utc)
    await db.commit()


def _normalize_attributes(raw: object) -> list[dict]:
    """Return attribute dicts from raw value.

    OPS sometimes returns attributes as a JSON string.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, list) else []
        except Exception:
            return []
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]
    return []


async def _upsert_options(
    db: AsyncSession, product_id: UUID, options: list[OptionIngest]
) -> None:
    """Upsert product_options by (product_id, option_key).

    Attributes are delete-and-reinsert per option (titles can change between syncs).
    """
    for opt in options:
        stmt = (
            pg_insert(ProductOption)
            .values(
                product_id=product_id,
                option_key=opt.option_key,
                title=opt.title,
                options_type=opt.options_type,
                sort_order=opt.sort_order,
                master_option_id=opt.master_option_id,
                ops_option_id=opt.ops_option_id,
                required=opt.required,
                status=1,
            )
            .on_conflict_do_update(
                index_elements=["product_id", "option_key"],
                set_={
                    "title": opt.title,
                    "options_type": opt.options_type,
                    "sort_order": opt.sort_order,
                    "master_option_id": opt.master_option_id,
                    "ops_option_id": opt.ops_option_id,
                    "required": opt.required,
                },
            )
            .returning(ProductOption.id)
        )
        option_id = (await db.execute(stmt)).scalar_one()

        await db.execute(
            ProductOptionAttribute.__table__.delete().where(
                ProductOptionAttribute.product_option_id == option_id
            )
        )

        raw_attrs = opt.attributes
        if isinstance(raw_attrs, list):
            attrs = [a.model_dump() for a in raw_attrs]
        else:
            attrs = _normalize_attributes(raw_attrs)

        for attr in attrs:
            title = attr.get("title")
            if not title:
                continue
            db.add(
                ProductOptionAttribute(
                    product_option_id=option_id,
                    title=str(title),
                    sort_order=int(attr.get("sort_order") or 0),
                    ops_attribute_id=attr.get("ops_attribute_id"),
                    status=1,
                )
            )


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------

@router.post(
    "/{supplier_id}/categories",
    response_model=IngestResult,
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_categories(
    supplier_id: UUID,
    batch: list[CategoryIngest],
    db: AsyncSession = Depends(get_db),
):
    """Two-pass upsert: write rows first, then resolve parent_external_id → parent_id.

    Two passes avoid FK ordering problems when children appear before parents
    in the batch.
    """
    supplier = await _load_active_supplier(supplier_id, db)
    job = await _start_sync_job(db, supplier, "categories")

    # Pass 1: upsert all rows without parent wiring.
    for cat in batch:
        stmt = pg_insert(Category).values(
            supplier_id=supplier.id,
            external_id=cat.external_id,
            name=cat.name,
            sort_order=cat.sort_order,
        ).on_conflict_do_update(
            index_elements=["supplier_id", "external_id"],
            set_={"name": cat.name, "sort_order": cat.sort_order},
        )
        await db.execute(stmt)
    await db.flush()

    # Pass 2: resolve parent_external_id → parent_id on rows that have a parent.
    ext_to_id = {
        c.external_id: c.id
        for c in (
            await db.execute(
                select(Category).where(Category.supplier_id == supplier.id)
            )
        ).scalars().all()
    }
    for cat in batch:
        if cat.parent_external_id:
            parent_id = ext_to_id.get(cat.parent_external_id)
            if parent_id is not None:
                await db.execute(
                    update(Category)
                    .where(
                        Category.supplier_id == supplier.id,
                        Category.external_id == cat.external_id,
                    )
                    .values(parent_id=parent_id)
                )

    await _finish_sync_job(db, job, len(batch))
    return IngestResult(
        sync_job_id=job.id, records_processed=len(batch), status="completed"
    )


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------

@router.post(
    "/{supplier_id}/products",
    response_model=IngestResult,
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_products(
    supplier_id: UUID,
    batch: list[ProductIngest],
    db: AsyncSession = Depends(get_db),
):
    """Upsert products + variants + images. Idempotent via ON CONFLICT DO UPDATE.

    Variants not present in this batch are preserved (partial syncs are common).
    Full-resync behavior (delete missing variants) will be added later behind
    an explicit `?replace=true` flag.
    """
    supplier = await _load_active_supplier(supplier_id, db)
    job = await _start_sync_job(db, supplier, "products")

    # Preload existing categories once for external_id → id lookup.
    ext_to_cat_id = {
        c.external_id: c.id
        for c in (
            await db.execute(select(Category).where(Category.supplier_id == supplier.id))
        ).scalars().all()
    }

    now = datetime.now(timezone.utc)

    for item in batch:
        category_id = (
            ext_to_cat_id.get(item.category_external_id)
            if item.category_external_id
            else None
        )
        product_stmt = pg_insert(Product).values(
            supplier_id=supplier.id,
            supplier_sku=item.supplier_sku,
            product_name=item.product_name,
            brand=item.brand,
            category=item.category_name,
            category_id=category_id,
            description=item.description,
            product_type=item.product_type,
            image_url=item.image_url,
            ops_product_id=item.ops_product_id,
            external_catalogue=item.external_catalogue,
            last_synced=now,
        ).on_conflict_do_update(
            index_elements=["supplier_id", "supplier_sku"],
            set_={
                "product_name": item.product_name,
                "brand": item.brand,
                "category": item.category_name,
                "category_id": category_id,
                "description": item.description,
                "product_type": item.product_type,
                "image_url": item.image_url,
                "ops_product_id": item.ops_product_id,
                "external_catalogue": item.external_catalogue,
                "last_synced": now,
            },
        ).returning(Product.id)
        product_id = (await db.execute(product_stmt)).scalar_one()

        for v in item.variants:
            variant_stmt = pg_insert(ProductVariant).values(
                product_id=product_id,
                color=v.color,
                size=v.size,
                sku=v.sku,
                base_price=v.base_price,
                inventory=v.inventory,
                warehouse=v.warehouse,
            ).on_conflict_do_update(
                index_elements=["product_id", "color", "size"],
                set_={
                    "sku": v.sku,
                    "base_price": v.base_price,
                    "inventory": v.inventory,
                    "warehouse": v.warehouse,
                },
            )
            await db.execute(variant_stmt)

        for idx, img in enumerate(item.images):
            image_stmt = pg_insert(ProductImage).values(
                product_id=product_id,
                url=img.url,
                image_type=img.image_type,
                color=img.color,
                sort_order=img.sort_order or idx,
            ).on_conflict_do_update(
                index_elements=["product_id", "url"],
                set_={
                    "image_type": img.image_type,
                    "color": img.color,
                    "sort_order": img.sort_order or idx,
                },
            )
            await db.execute(image_stmt)

        if item.options:
            await _upsert_options(db, product_id, item.options)

    await _finish_sync_job(db, job, len(batch))
    return IngestResult(
        sync_job_id=job.id, records_processed=len(batch), status="completed"
    )


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

@router.post(
    "/{supplier_id}/inventory",
    response_model=IngestResult,
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_inventory(
    supplier_id: UUID,
    batch: list[InventoryIngest],
    db: AsyncSession = Depends(get_db),
):
    """Update variant inventory + warehouse. Tolerant of stale SKUs (silent skip)."""
    supplier = await _load_active_supplier(supplier_id, db)
    job = await _start_sync_job(db, supplier, "inventory")

    products = (
        await db.execute(
            select(Product.id, Product.supplier_sku).where(
                Product.supplier_id == supplier.id
            )
        )
    ).all()
    sku_to_product_id = {row.supplier_sku: row.id for row in products}

    for item in batch:
        product_id = sku_to_product_id.get(item.supplier_sku)
        if product_id is None:
            continue
        await db.execute(
            update(ProductVariant)
            .where(
                ProductVariant.product_id == product_id,
                ProductVariant.sku == item.part_id,
            )
            .values(inventory=item.quantity_available, warehouse=item.warehouse)
        )

    await _finish_sync_job(db, job, len(batch))
    return IngestResult(
        sync_job_id=job.id, records_processed=len(batch), status="completed"
    )


# ---------------------------------------------------------------------------
# Pricing
# ---------------------------------------------------------------------------

@router.post(
    "/{supplier_id}/pricing",
    response_model=IngestResult,
    dependencies=[Depends(require_ingest_secret)],
)
async def ingest_pricing(
    supplier_id: UUID,
    batch: list[PriceIngest],
    db: AsyncSession = Depends(get_db),
):
    """Update variant base_price. Tolerant of stale SKUs (silent skip)."""
    supplier = await _load_active_supplier(supplier_id, db)
    job = await _start_sync_job(db, supplier, "pricing")

    products = (
        await db.execute(
            select(Product.id, Product.supplier_sku).where(
                Product.supplier_id == supplier.id
            )
        )
    ).all()
    sku_to_product_id = {row.supplier_sku: row.id for row in products}

    for item in batch:
        product_id = sku_to_product_id.get(item.supplier_sku)
        if product_id is None:
            continue
        await db.execute(
            update(ProductVariant)
            .where(
                ProductVariant.product_id == product_id,
                ProductVariant.sku == item.part_id,
            )
            .values(base_price=item.base_price)
        )

    await _finish_sync_job(db, job, len(batch))
    return IngestResult(
        sync_job_id=job.id, records_processed=len(batch), status="completed"
    )
