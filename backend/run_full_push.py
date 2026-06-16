"""Run ONE real full push of a SanMar product through the actual gateway
pipeline (execute_push) — proves variants + pricing + auto-category populate.
Creates a ProductPushLog row then runs execute_push (the same engine the UI uses).
Run: python run_full_push.py [SKU]   (default KP155)
"""
from __future__ import annotations
import asyncio, sys
from collections import Counter
from sqlalchemy import select
from database import async_session
from modules.customers.models import Customer
from modules.catalog.models import Product
from modules.suppliers.models import Supplier
from modules.push_log.models import ProductPushLog
from modules.ops_push.gateway import execute_push

SKU = sys.argv[1] if len(sys.argv) > 1 else "KP155"

async def main():
    async with async_session() as db:
        cust = (await db.execute(select(Customer).where(Customer.name == "visualgraphx"))).scalars().first()
        sm = (await db.execute(select(Supplier).where(Supplier.slug == "sanmar"))).scalars().first()
        p = (await db.execute(select(Product).where(
            Product.supplier_id == sm.id, Product.supplier_sku == SKU))).scalars().first()
        if not p:
            print(f"No SanMar product {SKU}"); return
        log = ProductPushLog(
            product_id=p.id, customer_id=cust.id, status="accepted",
            supplier_slug="sanmar", supplier_sku=SKU, dry_run=False,
        )
        db.add(log)
        await db.commit()
        push_id = log.id
        print(f"Created push_log {push_id} for {SKU} — running full push via execute_push()...")

    await execute_push(push_id)

    async with async_session() as db:
        log = await db.get(ProductPushLog, push_id)
        print(f"\nfinal status   : {log.status}")
        print(f"ops_product_id : {log.ops_product_id}")
        print(f"error          : {log.error}")
        if log.step_results:
            c = Counter(s.get("mutation") for s in log.step_results)
            print(f"steps executed : {dict(c)}")

if __name__ == "__main__":
    asyncio.run(main())
