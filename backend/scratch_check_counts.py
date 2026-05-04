import asyncio
from database import async_session
from sqlalchemy import select, func
from modules.catalog.models import Product
from modules.suppliers.models import Supplier
from modules.customers.models import Customer
from modules.push_mappings.models import PushMapping

async def check():
    async with async_session() as db:
        print("--- Supplier Product Counts ---")
        suppliers = await db.execute(select(Supplier))
        for s in suppliers.scalars():
            count = await db.execute(select(func.count(Product.id)).where(Product.supplier_id == s.id))
            print(f"Supplier: {s.name} | Products in Catalog: {count.scalar()}")

        print("\n--- Storefront (Customer) Pushed Product Counts ---")
        customers = await db.execute(select(Customer))
        for c in customers.scalars():
            count = await db.execute(select(func.count(PushMapping.id)).where(PushMapping.customer_id == c.id))
            print(f"Storefront: {c.name} | Pushed Products: {count.scalar()}")

if __name__ == "__main__":
    asyncio.run(check())
