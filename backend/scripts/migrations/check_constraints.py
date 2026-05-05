import asyncio
from sqlalchemy import text
from database import async_session

async def main():
    async with async_session() as db:
        # Get full index definitions
        r = await db.execute(text("""
            SELECT indexname, indexdef
            FROM pg_indexes
            WHERE tablename = 'product_variants'
        """))
        for row in r.fetchall():
            print(f"Index: {row[0]}")
            print(f"  Def: {row[1]}")
            print()

        # Check which ON CONFLICT would work - does (product_id, sku) have a unique constraint?
        r2 = await db.execute(text("""
            SELECT conname, contype, pg_get_constraintdef(oid)
            FROM pg_constraint
            WHERE conrelid = 'product_variants'::regclass
        """))
        print("Constraints on product_variants:")
        for row in r2.fetchall():
            print(f"  Name: {row[0]}, Type: {row[1]}, Def: {row[2]}")

if __name__ == "__main__":
    asyncio.run(main())
