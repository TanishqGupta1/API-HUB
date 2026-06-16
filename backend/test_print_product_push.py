"""ONE-PRODUCT verification of the product_type fix.

1. Builds the push payload for one SanMar product using the REAL (now fixed)
   payload_builder code (dry-run = no OPS write yet) and prints the product_type
   it will send.
2. Pushes JUST the setProduct step to OPS staging (creates one product).
3. Reads it back and confirms product_type is now the print-product value.

This DOES create one product on the staging storefront (the user approved a
single test push). It does not touch the other ~2985 SanMar products.

Run: python test_print_product_push.py
"""
from __future__ import annotations
import asyncio
from sqlalchemy import select
from database import async_session
from modules.customers.models import Customer
from modules.catalog.models import Product
from modules.suppliers.models import Supplier
from modules.ops_client.client import OpsAuth, OpsGraphQLClient
from modules.ops_client import mutations
from modules.ops_push.payload_builder import build_push_payload

_READBACK = ('query D($id:Int){ productsDetails(products_id:$id){ products { '
             'product_id product_name product_type predefined_product_type main_sku } } }')


async def main():
    async with async_session() as db:
        cust = (await db.execute(select(Customer).where(Customer.name == "visualgraphx"))).scalars().first()
        auth = OpsAuth(base_url=cust.ops_base_url, token_url=cust.ops_token_url,
                       client_id=cust.ops_client_id, client_secret=cust.ops_auth_config["client_secret"])
        sanmar = (await db.execute(select(Supplier).where(Supplier.slug == "sanmar"))).scalars().first()
        candidates = (await db.execute(
            select(Product.id, Product.supplier_sku, Product.product_name)
            .where(Product.supplier_id == sanmar.id)
            .where(Product.archived_at.is_(None))
            .limit(15)
        )).all()

        chosen, payload, setproduct_vars = None, None, None
        for pid, sku, name in candidates:
            try:
                payload = await build_push_payload(db, cust.id, pid, dry_run=True)
            except Exception as e:
                print(f"  skip {sku}: build failed ({type(e).__name__})")
                continue
            step = next((s for s in payload.plan if s.mutation == "setProduct"), None)
            if step:
                chosen, setproduct_vars = (pid, sku, name), step.variables
                break

    if not setproduct_vars:
        print("Could not build a payload for any SanMar product."); return

    pid, sku, name = chosen
    inp = setproduct_vars["inputs"][0]
    print(f"# Test product: {sku}  ({name})")
    print(f"# push_mode: {payload.push_mode}")
    print(f"# --- setProduct values our code will send (THE FIX) ---")
    for k in ("product_type", "predefined_product_type", "product_service_type",
              "price_defining_method", "products_title", "main_sku"):
        if k in inp:
            print(f"    {k} = {inp[k]!r}")
    print()

    # ---- LIVE: push just the setProduct step ----
    async with OpsGraphQLClient(auth) as client:
        print("Pushing setProduct to staging...")
        res = await client.execute(mutations._SET_PRODUCT, variables=setproduct_vars)
        if not res.ok:
            print(f"  PUSH FAILED: {res.ops_error_code} {res.ops_error_message}"); return
        data = mutations._unwrap_list(res.data, "setProduct")
        new_id = data.get("id")
        print(f"  OPS response: result={data.get('result')} message={data.get('message')!r} id={new_id}")
        if not new_id:
            print("  No product id returned — cannot read back."); return

        print(f"\nReading product {new_id} back from OPS...")
        rb = await client.execute(_READBACK, variables={"id": int(new_id)})
        rows = ((rb.data or {}).get("productsDetails") or {}).get("products") or []
        if rows:
            p = rows[0]
            pt = p.get("product_type")
            print(f"  product_type      = {pt!r}")
            print(f"  predefined_type   = {p.get('predefined_product_type')!r}")
            print(f"  main_sku          = {p.get('main_sku')!r}")
            verdict = "PRINT PRODUCT ✅" if (pt and pt not in ("0", "15") and any(c in str(pt) for c in "123")) else "still Ready-to-Buy ❌"
            print(f"\n  VERDICT: {verdict}  (OPS product id {new_id})")
        else:
            print("  read-back returned no rows")


if __name__ == "__main__":
    asyncio.run(main())
