import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

async def main():
    engine = create_async_engine("postgresql+asyncpg://vg_user:vg_pass@127.0.0.1:5432/vg_hub")
    async with AsyncSession(engine) as db:
        r = await db.execute(text("SELECT id, supplier_sku, product_name FROM products WHERE supplier_sku='L420'"))
        for row in r:
            print("PRODUCT:", row)

        r = await db.execute(text("SELECT id, name FROM customers LIMIT 5"))
        for row in r:
            print("CUSTOMER:", row)

        r = await db.execute(text("SELECT id, name, raw_key FROM integration_keys LIMIT 5"))
        for row in r:
            print("INTKEY:", row)

        r = await db.execute(text(
            "SELECT pm.id, pm.customer_id, pm.source_product_id, pm.target_ops_product_id "
            "FROM push_mappings pm JOIN products p ON pm.source_product_id = p.id "
            "WHERE p.supplier_sku='L420'"
        ))
        for row in r:
            print("PUSHMAPPING:", row)

    await engine.dispose()

asyncio.run(main())
