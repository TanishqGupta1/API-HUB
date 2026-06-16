"""Clear stale push_mappings for L420 and trigger a live push."""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import text

from modules.ops_push.gateway import execute_push
from modules.ops_push.service import prepare_push_intent
from modules.integrations.admin_proxy import get_or_create_admin_proxy_key
from modules.integrations.schemas import PushRequest, PushRequestTarget, PushRequestSource

DB_URL = "postgresql+asyncpg://vg_user:vg_pass@127.0.0.1:5432/vg_hub"

PRODUCT_ID = "39160830-f626-418b-86ec-99156851df19"  # L420

async def main():
    engine = create_async_engine(DB_URL)
    async with AsyncSession(engine) as db:

        # 1. Find the right customer (the one with ops_base_url pointing to visualgraphx)
        r = await db.execute(text(
            "SELECT id, name FROM customers WHERE name NOT IN "
            "('inventory_sync_v2','pricing_update','delta_product_ingest','full_catalog_push') "
            "ORDER BY name"
        ))
        customers = r.fetchall()
        print("Customers:")
        for c in customers:
            print(f"  {c.id}  {c.name}")

        # 2. Find existing push_mappings for L420
        r = await db.execute(text(
            "SELECT pm.id, pm.customer_id, pm.target_ops_product_id "
            "FROM push_mappings pm "
            f"WHERE pm.source_product_id = '{PRODUCT_ID}'"
        ))
        mappings = r.fetchall()
        print("\nExisting push_mappings for L420:")
        for m in mappings:
            print(f"  mapping_id={m.id}  customer={m.customer_id}  ops_id={m.target_ops_product_id}")

        # 3. Delete stale push_mappings row (target_ops_product_id is NOT NULL so can't set to null)
        result = await db.execute(text(
            f"DELETE FROM push_mappings "
            f"WHERE source_product_id = '{PRODUCT_ID}' "
            f"AND target_ops_product_id IN (581, 582)"
        ))
        await db.commit()
        print(f"\nDeleted {result.rowcount} stale push_mappings row(s)")

        # 4. Use visualgraphx customer (confirmed from push log)
        customer_id = "a2b91bac-10a0-4c0a-b284-cbac991250bf"
        print(f"\nUsing customer_id: {customer_id}")

        # 5. Get supplier slug for L420
        r = await db.execute(text(
            f"SELECT s.slug FROM products p JOIN suppliers s ON p.supplier_id = s.id "
            f"WHERE p.id = '{PRODUCT_ID}'"
        ))
        supplier_slug = r.scalar_one()
        print(f"Supplier slug: {supplier_slug}")

        # 6. Prepare push intent using admin proxy key
        proxy_key = await get_or_create_admin_proxy_key(db)

        from modules.integrations.schemas import PushRequestProductRef
        req = PushRequest(
            source=PushRequestSource(supplier_slug=supplier_slug),
            target=PushRequestTarget(customer_id=customer_id),
            product_ref=PushRequestProductRef(supplier_sku="L420"),
            dry_run=False,
        )

        accepted = await prepare_push_intent(req, proxy_key, db, idempotency_key=None)
        print(f"\nPush accepted: push_log_id={accepted.push_log_id}  status={accepted.status}")

    await engine.dispose()

    # 7. Execute push (opens its own session)
    if accepted.status in ("accepted", "queued"):
        print("\nExecuting push...")
        await execute_push(accepted.push_log_id)
        print("Push complete — check push log in API-HUB for results.")
    else:
        print(f"\nPush not executed — status was: {accepted.status}")

asyncio.run(main())
