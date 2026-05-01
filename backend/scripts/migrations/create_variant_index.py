import asyncio
from sqlalchemy import text
from database import async_session

async def main():
    async with async_session() as db:
        # Check existing indexes
        r = await db.execute(text(
            "SELECT indexname FROM pg_indexes WHERE tablename = 'product_variants'"
        ))
        indexes = [row[0] for row in r.fetchall()]
        print("Current indexes on product_variants:")
        for i in indexes:
            print(f"  - {i}")

        if "uq_product_variants_product_sku" not in indexes:
            print("Creating unique index on (product_id, sku)...")
            await db.execute(text(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_product_variants_product_sku "
                "ON product_variants(product_id, sku) WHERE sku IS NOT NULL"
            ))
            await db.commit()
            print("Done.")
        else:
            print("Index already exists — nothing to do.")

if __name__ == "__main__":
    asyncio.run(main())
