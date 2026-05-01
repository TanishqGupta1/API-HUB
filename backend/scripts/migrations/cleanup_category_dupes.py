"""Clean up duplicate Category rows with same name but different external_id."""
import asyncio, re
from sqlalchemy import text
from database import async_session

async def main():
    async with async_session() as db:
        # Find duplicate category names per supplier
        r = await db.execute(text("""
            SELECT supplier_id, name, COUNT(*) as cnt
            FROM categories
            GROUP BY supplier_id, name
            HAVING COUNT(*) > 1
        """))
        dupes = r.fetchall()
        print(f"Found {len(dupes)} duplicate (supplier_id, name) category groups")

        for row in dupes:
            print(f"  supplier={row[0]} name={row[1]} count={row[2]}")

        if not dupes:
            print("No category duplicates.")
            return

        # Keep the row with the slug-style external_id (most recent correct one)
        deleted = await db.execute(text("""
            DELETE FROM categories
            WHERE id NOT IN (
                SELECT DISTINCT ON (supplier_id, name) id
                FROM categories
                ORDER BY supplier_id, name, id DESC
            )
        """))
        await db.commit()
        print(f"Deleted {deleted.rowcount} duplicate category rows.")

if __name__ == "__main__":
    asyncio.run(main())
