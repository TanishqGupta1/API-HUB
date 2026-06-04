"""Targeted SanMar sync — pulls 5 specific styles end-to-end and persists.

Each style: product detail + pricing tiers + media + inventory → DB.
Uses the same adapter + normalizer + persistence as the regular import job,
so this is a true end-to-end validation of the pipeline on real data.

Run from backend/ with the venv active:
    python scripts/sync_sanmar_5_skus.py
"""
from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from sqlalchemy import select

from database import async_session
from modules.catalog.persistence import persist_product
from modules.import_jobs.base import ProductRef
from modules.promostandards.sanmar_adapter import SanMarAdapter
from modules.suppliers.models import Supplier


SANMAR_SUPPLIER_ID = UUID("a73a8445-2f08-4293-9625-b3e480ddc1da")
SKUS = ["PC61", "L500", "ST350", "PC54", "PC78H"]


async def sync_one(supplier, sku: str) -> dict:
    """Hydrate one SKU and persist. Uses a dedicated session so a failed
    sync of one SKU doesn't poison the transaction for later ones."""
    async with async_session() as db:
        # Re-attach supplier to this session for the adapter
        local_supplier = await db.get(Supplier, supplier.id)
        adapter = SanMarAdapter(supplier=local_supplier, db=db)
        ref = ProductRef(supplier_sku=sku)
        ingest = await adapter.hydrate_product(ref)

        priced_variants = [v for v in ingest.variants if v.base_price is not None]
        inv_variants = [v for v in ingest.variants if v.inventory is not None]
        total_stock = sum((v.inventory or 0) for v in inv_variants)

        await persist_product(db, supplier.id, ingest, category_id=None)
        await db.commit()

    return {
        "sku": sku,
        "name": ingest.product_name,
        "n_variants": len(ingest.variants),
        "n_priced": len(priced_variants),
        "n_with_inventory": len(inv_variants),
        "total_stock": total_stock,
        "min_price": min((float(v.base_price) for v in priced_variants), default=None),
        "max_price": max((float(v.base_price) for v in priced_variants), default=None),
        "n_images": len(ingest.images or []),
    }


async def main() -> int:
    async with async_session() as setup_db:
        supplier = await setup_db.get(Supplier, SANMAR_SUPPLIER_ID)
        if supplier is None:
            print("ERROR: SanMar supplier missing", file=sys.stderr)
            return 2

    print(f"Syncing {len(SKUS)} SanMar styles end-to-end (fetch → normalize → persist)\n")
    results: list[dict] = []
    for sku in SKUS:
        print(f"━━━ {sku} ━━━")
        try:
            summary = await sync_one(supplier, sku)
        except Exception as exc:  # noqa: BLE001
            print(f"  EXC: {type(exc).__name__}: {exc}")
            continue
        print(f"  ✓ {summary['name']}")
        print(f"    variants:  {summary['n_variants']} ({summary['n_priced']} priced, {summary['n_with_inventory']} w/ inventory)")
        if summary["min_price"] is not None:
            print(f"    price:     ${summary['min_price']:.2f} – ${summary['max_price']:.2f}")
        print(f"    stock:     {summary['total_stock']:,} units across {summary['n_with_inventory']} variants")
        print(f"    images:    {summary['n_images']}")
        print()
        results.append(summary)

    # Verify by querying back from DB (fresh session — earlier ones are closed)
    async with async_session() as verify_db:
        from modules.catalog.models import Product, ProductVariant
        from sqlalchemy import func
        for r in results:
            db_count = (await verify_db.execute(
                select(func.count()).select_from(ProductVariant)
                .join(Product, Product.id == ProductVariant.product_id)
                .where(Product.supplier_sku == r["sku"], Product.supplier_id == SANMAR_SUPPLIER_ID)
            )).scalar()
            r["db_variants"] = db_count

    print("━━━ DB Verification ━━━")
    for r in results:
        ok = "✓" if r["db_variants"] == r["n_variants"] else "✗"
        print(f"  {ok} {r['sku']:7s} fetched={r['n_variants']:4d}  in_db={r['db_variants']:4d}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
