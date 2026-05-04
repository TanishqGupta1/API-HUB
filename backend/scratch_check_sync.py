import asyncio
from database import async_session
from sqlalchemy import select, func
from modules.catalog.models import Product
from modules.suppliers.models import Supplier

async def check():
    async with async_session() as db:
        print("--- SanMar Sync Status ---")
        supplier_res = await db.execute(select(Supplier).where(Supplier.name == "SanMar"))
        s = supplier_res.scalar_one_or_none()
        if s:
            total = await db.execute(select(func.count(Product.id)).where(Product.supplier_id == s.id))
            synced = await db.execute(select(func.count(Product.id)).where(Product.supplier_id == s.id, Product.last_synced.is_not(None)))
            print(f"Total SanMar Products: {total.scalar()}")
            print(f"Synced SanMar Products (last_synced NOT NULL): {synced.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
