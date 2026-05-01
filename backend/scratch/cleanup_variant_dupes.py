"""
Cleanup script for duplicate product_variants rows.
Runs BEFORE the unique index can be created safely.
"""
import asyncio
from sqlalchemy import text
from database import async_session


async def main():
    async with async_session() as db:
        # Step 1: Check for duplicates
        dup_check = await db.execute(text("""
            SELECT product_id, sku, COUNT(*) as cnt
            FROM product_variants
            WHERE sku IS NOT NULL
            GROUP BY product_id, sku
            HAVING COUNT(*) > 1
        """))
        dupes = dup_check.fetchall()
        print(f"Found {len(dupes)} duplicate (product_id, sku) groups")

        if not dupes:
            print("No duplicates — safe to create index.")
            return

        # Step 2: Delete duplicates, keeping only the row with the MAX id (most recent)
        result = await db.execute(text("""
            DELETE FROM product_variants
            WHERE id NOT IN (
                SELECT MAX(id)
                FROM product_variants
                WHERE sku IS NOT NULL
                GROUP BY product_id, sku
            )
            AND sku IS NOT NULL
        """))
        await db.commit()
        print(f"Deleted {result.rowcount} duplicate variant rows.")

        # Step 3: Verify
        verify = await db.execute(text("""
            SELECT COUNT(*) FROM product_variants
            WHERE sku IS NOT NULL
            GROUP BY product_id, sku
            HAVING COUNT(*) > 1
        """))
        remaining = len(verify.fetchall())
        print(f"Remaining duplicates after cleanup: {remaining}")
        
        if remaining == 0:
            print("Clean! Ready to create unique index.")


if __name__ == "__main__":
    asyncio.run(main())
