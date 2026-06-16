"""Push K420 (Port Authority Heavyweight Cotton Pique Polo) to Print Products section."""
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

PRODUCT_ID = "22f47b56-60ce-420e-8d08-350c823a38e6"  # K420
CUSTOMER_ID = "a2b91bac-10a0-4c0a-b284-cbac991250bf"  # visualgraphx

async def main():
    engine = create_async_engine(DB_URL)
    async with AsyncSession(engine) as db:

        # Cancel any existing push logs for K420
        r = await db.execute(text(
            f"UPDATE product_push_log SET status = 'canceled' "
            f"WHERE product_id = '{PRODUCT_ID}' AND status NOT IN ('canceled') "
            f"RETURNING id"
        ))
        canceled = r.fetchall()
        if canceled:
            print(f"Canceled {len(canceled)} prior push log(s) for K420")
        await db.commit()

        proxy_key = await get_or_create_admin_proxy_key(db)

        from modules.integrations.schemas import PushRequestProductRef
        req = PushRequest(
            source=PushRequestSource(supplier_slug="sanmar"),
            target=PushRequestTarget(customer_id=CUSTOMER_ID),
            product_ref=PushRequestProductRef(supplier_sku="K420"),
            dry_run=False,
        )

        accepted = await prepare_push_intent(req, proxy_key, db, idempotency_key=None)
        print(f"Push accepted: push_log_id={accepted.push_log_id}  status={accepted.status}")

    await engine.dispose()

    if accepted.status in ("accepted", "queued"):
        print("Executing push (K420 -> Print Products)...")
        await execute_push(accepted.push_log_id)
        print("Push complete.")
    else:
        print(f"Push not executed — status: {accepted.status}")

asyncio.run(main())
