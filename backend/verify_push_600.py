"""Read product 600 back from OPS after the full push — confirm variants,
options, pricing, type, and category are populated. Read-only."""
from __future__ import annotations
import asyncio
from sqlalchemy import select, text
from database import async_session
from modules.customers.models import Customer
from modules.ops_client.client import OpsAuth, OpsGraphQLClient

DETAILS = 'query($id:Int){ productsDetails(products_id:$id){ products { product_id product_name product_type predefined_product_type } } }'
SIZES   = 'query($id:Int){ productSize(products_id:$id){ totalProductSize } }'
OPTS    = 'query($id:Int){ productAdditionalOptions(products_id:$id){ totalProductAdditionalOptions productAdditionalOptions { title } } }'
PRICE   = 'query($id:Int){ productPrice(products_id:$id){ totalProductPrice } }'

async def q(client, query, label):
    r = await client.execute(query, variables={"id": 600})
    if not r.ok:
        print(f"  {label}: ERR {r.ops_error_code} {r.ops_error_message}")
        return None
    return r.data

async def main():
    async with async_session() as db:
        c = (await db.execute(select(Customer).where(Customer.name == "visualgraphx"))).scalars().first()
        auth = OpsAuth(base_url=c.ops_base_url, token_url=c.ops_token_url,
                       client_id=c.ops_client_id, client_secret=c.ops_auth_config["client_secret"])
        cust_id = str(c.id)

    async with OpsGraphQLClient(auth) as client:
        d = await q(client, DETAILS, "details")
        if d:
            p = (d.get("productsDetails") or {}).get("products") or [{}]
            p = p[0] if p else {}
            print(f"  product_type   = {p.get('product_type')!r}  (1,2,3 = Print Product)")
            print(f"  product_name   = {p.get('product_name')!r}")
        s = await q(client, SIZES, "sizes")
        if s:
            print(f"  variants/sizes = {(s.get('productSize') or {}).get('totalProductSize')}")
        pr = await q(client, PRICE, "price")
        if pr:
            print(f"  price rows     = {(pr.get('productPrice') or {}).get('totalProductPrice')}")
        o = await q(client, OPTS, "options")
        if o:
            blk = o.get("productAdditionalOptions") or {}
            print(f"  options        = {blk.get('totalProductAdditionalOptions')}")
            titles = [x.get("title") for x in (blk.get("productAdditionalOptions") or [])][:8]
            print(f"  option titles  = {titles}")

    async with async_session() as db:
        rows = (await db.execute(text(
            "SELECT category_key, ops_category_id FROM ops_category_mappings WHERE customer_id=:c"
        ), {"c": cust_id})).all()
        print(f"\n  category cache = {[(r[0], r[1]) for r in rows]}")

if __name__ == "__main__":
    asyncio.run(main())
