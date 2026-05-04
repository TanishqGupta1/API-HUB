import asyncio
from database import async_session
from sqlalchemy import select
from modules.suppliers.models import Supplier
from modules.customers.models import Customer

async def check():
    async with async_session() as db:
        sups = (await db.execute(select(Supplier.name, Supplier.id))).all()
        custs = (await db.execute(select(Customer.name, Customer.id))).all()
        print("Suppliers:")
        for s in sups:
            print(f"  - '{s.name}' (ID: {s.id})")
        print("Customers (Storefronts):")
        for c in custs:
            print(f"  - '{c.name}' (ID: {c.id})")

if __name__ == "__main__":
    asyncio.run(check())
