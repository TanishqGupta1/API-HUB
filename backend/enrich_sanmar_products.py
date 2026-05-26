"""
One-time enrichment script for SanMar products.

Fixes 3 preflight blockers across all 177 SanMar products:
  1. Category - create Category rows from product.category text + link products
  2. Images   - seed ProductImage rows from product.image_url (already stored)
  3. Inventory - trigger the SanMar inventory SOAP sync via the running API
"""
import asyncio
import os
import re
import httpx
from datetime import datetime, timezone

from database import async_session
from sqlalchemy import select, update, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from modules.catalog.models import Category, Product, ProductImage
from modules.suppliers.models import Supplier


SANMAR_CODE = "SANMAR"
API_BASE    = os.getenv("API_BASE", "http://127.0.0.1:8000")
INGEST_SECRET = None  # filled from env below


async def fix_categories(db, supplier_id):
    """Create Category rows for each unique category text and link products."""
    # Get all distinct non-null category texts for SanMar
    rows = (await db.execute(
        select(Product.category)
        .where(Product.supplier_id == supplier_id, Product.category != None)
        .distinct()
    )).scalars().all()

    cat_texts = [r for r in rows if r]
    print(f"\n[CATEGORY] Found {len(cat_texts)} distinct category names")

    slug_to_id = {}
    for name in cat_texts:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        stmt = pg_insert(Category).values(
            supplier_id=supplier_id,
            external_id=slug,
            name=name,
            sort_order=0,
        ).on_conflict_do_update(
            index_elements=["supplier_id", "external_id"],
            set_={"name": name},
        ).returning(Category.id)
        cat_id = (await db.execute(stmt)).scalar_one()
        slug_to_id[name] = cat_id
        print(f"  ✓ category '{name}' → {cat_id}")

    await db.commit()

    # Link products that have category text but no category_id
    linked = 0
    for name, cat_id in slug_to_id.items():
        result = await db.execute(
            update(Product)
            .where(
                Product.supplier_id == supplier_id,
                Product.category == name,
                Product.category_id == None,
            )
            .values(category_id=cat_id)
        )
        linked += result.rowcount

    await db.commit()
    print(f"[CATEGORY] Linked {linked} products to categories")
    return len(slug_to_id)


async def fix_images(db, supplier_id):
    """Seed ProductImage rows from product.image_url for any product that has
    an image_url but no ProductImage rows yet."""
    products = (await db.execute(
        select(Product)
        .where(
            Product.supplier_id == supplier_id,
            Product.image_url != None,
        )
    )).scalars().all()

    seeded = 0
    skipped = 0
    for p in products:
        # Check if ProductImage rows already exist
        existing = (await db.execute(
            select(ProductImage.id).where(ProductImage.product_id == p.id).limit(1)
        )).scalar_one_or_none()
        if existing:
            skipped += 1
            continue

        stmt = pg_insert(ProductImage).values(
            product_id=p.id,
            url=p.image_url,
            supplier_image_url=p.image_url,
            image_type="front",
        ).on_conflict_do_nothing()
        await db.execute(stmt)
        seeded += 1

    await db.commit()
    print(f"\n[IMAGES] Seeded {seeded} ProductImage rows  (skipped {skipped} already had images)")
    return seeded


async def trigger_inventory_sync(supplier_id):
    """Hit the live API to kick off a SanMar inventory SOAP sync."""
    import os
    secret = os.getenv("INGEST_SHARED_SECRET", "")
    headers = {"X-Ingest-Secret": secret} if secret else {}

    print(f"\n[INVENTORY] Triggering SanMar inventory sync...")
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(
            f"{API_BASE}/api/sync/{supplier_id}/inventory",
            headers=headers,
        )
        if r.status_code in (200, 202):
            data = r.json()
            print(f"  ✓ job_id={data.get('job_id')}  status={data.get('status')}")
            return data.get("job_id")
        else:
            print(f"  ✗ HTTP {r.status_code}: {r.text[:200]}")
            return None


async def poll_job(job_id, timeout=300):
    """Poll sync job until done or timeout."""
    if not job_id:
        return
    print(f"[INVENTORY] Polling job {job_id} ...")
    async with httpx.AsyncClient(timeout=10) as client:
        for _ in range(timeout // 5):
            await asyncio.sleep(5)
            r = await client.get(f"{API_BASE}/api/sync-jobs/{job_id}")
            if r.status_code == 200:
                data = r.json()
                status = data.get("status")
                processed = data.get("records_processed", 0)
                print(f"  → {status}  ({processed} records)")
                if status in ("completed", "failed", "partial_success"):
                    if data.get("error_log"):
                        print(f"  error: {data['error_log'][:200]}")
                    return status
    print("  ✗ timed out")


async def recheck(db, supplier_id):
    """Print updated counts after enrichment."""
    total = (await db.execute(
        select(text("COUNT(*)")).select_from(Product).where(Product.supplier_id == supplier_id)
    )).scalar()
    no_cat = (await db.execute(
        select(text("COUNT(*)")).select_from(Product).where(
            Product.supplier_id == supplier_id, Product.category_id == None
        )
    )).scalar()
    has_img = (await db.execute(
        select(text("COUNT(DISTINCT product_id)")).select_from(ProductImage).where(
            ProductImage.product_id.in_(
                select(Product.id).where(Product.supplier_id == supplier_id)
            )
        )
    )).scalar()
    print(f"\n{'='*50}")
    print(f"AFTER ENRICHMENT — SanMar products ({total} total)")
    print(f"  Missing category:  {no_cat}")
    print(f"  Have images:       {has_img} / {total}")
    print(f"{'='*50}")


async def main():
    async with async_session() as db:
        sanmar = (await db.execute(
            select(Supplier).where(Supplier.promostandards_code == SANMAR_CODE)
        )).scalar_one_or_none()
        if not sanmar:
            print("SanMar supplier not found"); return

        supplier_id = sanmar.id
        print(f"SanMar supplier id: {supplier_id}")

        await fix_categories(db, supplier_id)
        await fix_images(db, supplier_id)

    job_id = await trigger_inventory_sync(supplier_id)
    await poll_job(job_id)

    async with async_session() as db:
        await recheck(db, supplier_id)


if __name__ == "__main__":
    asyncio.run(main())
