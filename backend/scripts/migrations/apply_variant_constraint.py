"""Apply the constraint migration directly to the running DB."""
import asyncio
from sqlalchemy import text
from database import async_session

async def main():
    async with async_session() as db:
        # Drop the old broken constraint
        print("Dropping old constraint uq_variant_product_color_size...")
        await db.execute(text(
            "ALTER TABLE product_variants DROP CONSTRAINT IF EXISTS uq_variant_product_color_size"
        ))
        await db.commit()
        print("Done.")

        # Drop the old partial index (created earlier, replaced by full constraint)
        print("Dropping partial index uq_product_variants_product_sku if it exists...")
        await db.execute(text(
            "DROP INDEX IF EXISTS uq_product_variants_product_sku"
        ))
        await db.commit()

        # Add the new UNIQUE constraint on (product_id, sku)
        # This handles NULLs correctly because NULL sku rows are excluded
        print("Adding new UNIQUE CONSTRAINT on (product_id, sku)...")
        await db.execute(text("""
            DO $$ BEGIN
              IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_product_variants_product_sku'
              ) THEN
                ALTER TABLE product_variants
                ADD CONSTRAINT uq_product_variants_product_sku UNIQUE (product_id, sku);
              END IF;
            END $$
        """))
        await db.commit()
        print("Constraint created successfully.")

        # Verify
        r = await db.execute(text("""
            SELECT indexname, indexdef FROM pg_indexes
            WHERE tablename = 'product_variants'
        """))
        print("\nFinal indexes on product_variants:")
        for row in r.fetchall():
            print(f"  - {row[0]}: {row[1]}")

if __name__ == "__main__":
    asyncio.run(main())
