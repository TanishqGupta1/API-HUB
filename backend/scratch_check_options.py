import asyncio
from database import async_session
from sqlalchemy import select
from modules.catalog.models import Product, ProductOption

async def check():
    async with async_session() as db:
        res = await db.execute(select(Product).where(Product.product_name.ilike('%Performance Tech Hoodie%')))
        products = res.scalars().all()
        for p in products:
            opts_res = await db.execute(select(ProductOption).where(ProductOption.product_id == p.id))
            opts = opts_res.scalars().all()
            print(f"Product: {p.product_name} (ID: {p.id}) | Options: {len(opts)}")
            for o in opts:
                print(f"  - Option: {o.title} (Key: {o.option_key})")

if __name__ == "__main__":
    asyncio.run(check())
