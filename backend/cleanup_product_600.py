"""Clean up the duplicated child records on OPS product 600 (KP155 test).
Deletes ALL additional options + sizes (a clean images-off re-push then
restores 21 colors + 1 size; the 72-image gallery is left untouched).
Read+delete only on product 600. Run: python cleanup_product_600.py
"""
from __future__ import annotations
import asyncio
from sqlalchemy import select
from database import async_session
from modules.customers.models import Customer
from modules.ops_client.client import OpsAuth, OpsGraphQLClient
from modules.ops_client import mutations

OPID = 600
OPTS_Q = 'query($id:Int){ productAdditionalOptions(products_id:$id){ productAdditionalOptions { prod_add_opt_id } totalProductAdditionalOptions } }'
SIZE_Q = 'query($id:Int){ productSize(products_id:$id){ productSize { size_id } totalProductSize } }'

async def main():
    async with async_session() as db:
        c = (await db.execute(select(Customer).where(Customer.name == "visualgraphx"))).scalars().first()
        auth = OpsAuth(base_url=c.ops_base_url, token_url=c.ops_token_url,
                       client_id=c.ops_client_id, client_secret=c.ops_auth_config["client_secret"])

    async with OpsGraphQLClient(auth) as client:
        # --- options ---
        r = await client.execute(OPTS_Q, variables={"id": OPID})
        opts = [o["prod_add_opt_id"] for o in
                ((r.data or {}).get("productAdditionalOptions") or {}).get("productAdditionalOptions") or []]
        print(f"deleting {len(opts)} additional options...")
        ok = err = 0
        for oid in opts:
            res = await client.execute(mutations._SET_ADDITIONAL_OPTION,
                variables={"inputs": [{"prod_add_opt_id": oid, "products_id": OPID, "delete": 1}]})
            ok += res.ok; err += (not res.ok)
            if not res.ok:
                print("   option delete err:", res.ops_error_message)
            await asyncio.sleep(0.1)
        print(f"   options: ok={ok} err={err}")

        # --- sizes ---
        r = await client.execute(SIZE_Q, variables={"id": OPID})
        sizes = [s["size_id"] for s in
                 ((r.data or {}).get("productSize") or {}).get("productSize") or []]
        print(f"deleting {len(sizes)} sizes...")
        ok = err = 0
        for sid in sizes:
            res = await client.execute(mutations._SET_PRODUCT_SIZE,
                variables={"inputs": [{"size_id": sid, "products_id": OPID, "delete": 1}]})
            ok += res.ok; err += (not res.ok)
            if not res.ok:
                print("   size delete err:", res.ops_error_message)
            await asyncio.sleep(0.1)
        print(f"   sizes: ok={ok} err={err}")

        # --- verify ---
        ro = await client.execute(OPTS_Q, variables={"id": OPID})
        rs = await client.execute(SIZE_Q, variables={"id": OPID})
        print("\nAFTER cleanup:")
        print("  options:", ((ro.data or {}).get("productAdditionalOptions") or {}).get("totalProductAdditionalOptions"))
        print("  sizes  :", ((rs.data or {}).get("productSize") or {}).get("totalProductSize"))

if __name__ == "__main__":
    asyncio.run(main())
