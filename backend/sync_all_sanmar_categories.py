"""Bulk-sync every SanMar category so Product.category text is populated.

Background: imports run per-category. Any product never reached by a category
import has Product.category=NULL, which blocks preflight. This script iterates
every entry in SANMAR_CATEGORIES and runs the same code path the UI uses
(POST /api/suppliers/{id}/import-category) directly, in-process. Sequential —
SanMar SOAP doesn't like parallel sessions.

Usage:
    cd backend && source .venv/bin/activate
    python sync_all_sanmar_categories.py
"""
import asyncio
from datetime import datetime, timezone

from sqlalchemy import select, func

from database import async_session
from modules.suppliers.models import Supplier
from modules.suppliers.service import get_cached_endpoints
from modules.suppliers.category_import import _run_category_import
from modules.promostandards.client import SANMAR_CATEGORIES, SANMAR_EXT_WSDL
from modules.promostandards.resolver import resolve_wsdl_url
from modules.sync_jobs.models import SyncJob
from modules.catalog.models import Product


LIMIT_PER_CATEGORY = 500


async def main() -> None:
    async with async_session() as db:
        sanmar = (await db.execute(
            select(Supplier).where(Supplier.promostandards_code == "SANMAR")
        )).scalar_one_or_none()
        if not sanmar:
            print("SanMar supplier not found"); return

        endpoints = await get_cached_endpoints(db, sanmar.id)
        wsdl_product = resolve_wsdl_url(endpoints, "product_data")
        wsdl_pricing = resolve_wsdl_url(endpoints, "ppc")
        wsdl_inventory = resolve_wsdl_url(endpoints, "inventory")
        wsdl_media = resolve_wsdl_url(endpoints, "media_content")

        if not wsdl_product:
            print("product_data WSDL missing from endpoint cache. "
                  "Hit Refresh Endpoints in the supplier page first.")
            return

        auth_config = dict(sanmar.auth_config or {})
        supplier_id = sanmar.id
        supplier_name = sanmar.name

        before_missing = (await db.execute(
            select(func.count()).select_from(Product).where(
                Product.supplier_id == supplier_id,
                Product.category.is_(None),
            )
        )).scalar()

    print(f"BEFORE: {before_missing} SanMar products missing category text")
    print(f"Running {len(SANMAR_CATEGORIES)} category imports (limit={LIMIT_PER_CATEGORY}):\n")

    for i, cat in enumerate(SANMAR_CATEGORIES, 1):
        print(f"[{i}/{len(SANMAR_CATEGORIES)}] {cat} ...", flush=True)

        # Create the SyncJob row in its own session so _run_category_import
        # can reload it from a fresh session (same pattern as the HTTP endpoint).
        async with async_session() as db:
            job = SyncJob(
                supplier_id=supplier_id,
                supplier_name=supplier_name,
                job_type=f"category:{cat}",
                status="queued",
                started_at=datetime.now(timezone.utc),
                records_processed=0,
            )
            db.add(job)
            await db.commit()
            await db.refresh(job)
            job_id = job.id

        try:
            await _run_category_import(
                job_id=job_id,
                supplier_id=supplier_id,
                auth_config=auth_config,
                wsdl_product=wsdl_product,
                wsdl_media=wsdl_media,
                category_name=cat,
                limit=LIMIT_PER_CATEGORY,
                extension_wsdl_url=SANMAR_EXT_WSDL,
                fetch_images=False,
                wsdl_pricing=wsdl_pricing,
                wsdl_inventory=wsdl_inventory,
            )
            async with async_session() as db:
                row = await db.get(SyncJob, job_id)
                processed = row.records_processed if row else 0
                status = row.status if row else "?"
            print(f"  → {status}, {processed} products", flush=True)
        except Exception as exc:
            print(f"  ✗ failed: {exc}", flush=True)

    async with async_session() as db:
        after_missing = (await db.execute(
            select(func.count()).select_from(Product).where(
                Product.supplier_id == supplier_id,
                Product.category.is_(None),
            )
        )).scalar()
        total = (await db.execute(
            select(func.count()).select_from(Product).where(
                Product.supplier_id == supplier_id,
            )
        )).scalar()

    print(f"\nAFTER: {after_missing} / {total} SanMar products still missing category")
    print(f"Filled {before_missing - after_missing} category fields.")


if __name__ == "__main__":
    asyncio.run(main())
