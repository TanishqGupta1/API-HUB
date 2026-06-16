"""Show what a FULL push (not my minimal test) would send for one SanMar product:
variants, pricing, options, images. Dry-run = safe, no OPS write.
Run: python inspect_full_payload.py
"""
from __future__ import annotations
import asyncio, os
from collections import Counter
from sqlalchemy import select
from database import async_session
from modules.customers.models import Customer
from modules.catalog.models import Product
from modules.suppliers.models import Supplier
from modules.ops_push.payload_builder import build_push_payload

async def main():
    async with async_session() as db:
        cust = (await db.execute(select(Customer).where(Customer.name == "visualgraphx"))).scalars().first()
        sanmar = (await db.execute(select(Supplier).where(Supplier.slug == "sanmar"))).scalars().first()
        prod = (await db.execute(
            select(Product).where(Product.supplier_id == sanmar.id, Product.supplier_sku == "KP155")
        )).scalars().first()
        if not prod:
            prod = (await db.execute(
                select(Product).where(Product.supplier_id == sanmar.id, Product.archived_at.is_(None)).limit(1)
            )).scalars().first()

        payload = await build_push_payload(db, cust.id, prod.id, dry_run=True)

    print(f"# Product {prod.supplier_sku} — {prod.product_name}")
    print(f"# OPS_PUSH_INCLUDE_IMAGES = {os.getenv('OPS_PUSH_INCLUDE_IMAGES', '0')}  (0 = images OFF)")
    print(f"# OPS_PUSH_INCLUDE_STOCK  = {os.getenv('OPS_PUSH_INCLUDE_STOCK', '0')}")
    print(f"# estimated_mutations = {payload.estimated_mutations}")
    print(f"# computed price rows  = {len(payload.computed_prices)}")
    print(f"# primary_image_url    = {payload.primary_image_url!r}")
    if payload.image_warnings:
        print(f"# image_warnings       = {payload.image_warnings}")
    print("\n# Full push plan — steps by mutation type:")
    counts = Counter(s.mutation for s in payload.plan)
    for mut, n in counts.most_common():
        print(f"    {mut:28} x {n}")
    print(f"\n# total steps = {len(payload.plan)}")

if __name__ == "__main__":
    asyncio.run(main())
