"""Read-only: compare a known-good PRINT product (309 Custom Pole Flag) against
our pushed SanMar products — to see what product_type / design fields differ.
Never mutates. Run: python inspect_ops_product309.py
"""
from __future__ import annotations
import asyncio
from sqlalchemy import select
from database import async_session
from modules.customers.models import Customer
from modules.catalog.models import Product
from modules.ops_client.client import OpsAuth, OpsGraphQLClient

_TYPE = """query T($name:String!){ __type(name:$name){ fields{ name type{kind name ofType{kind name ofType{kind name}}} } } }"""
_SCALARS = {"String", "Int", "Float", "Boolean", "ID"}

def _base(t):
    while t and t.get("ofType"):
        t = t["ofType"]
    return t or {}

async def scalar_fields(client, typename):
    r = await client.execute(_TYPE, variables={"name": typename})
    t = (r.data or {}).get("__type") or {}
    out = []
    for f in t.get("fields") or []:
        bt = _base(f["type"])
        if bt.get("kind") == "SCALAR" or bt.get("name") in _SCALARS:
            out.append(f["name"])
    return out

# The fields that decide "print product vs ready to buy" + design setup
KEY = ["product_id", "products_id", "product_name", "products_title", "main_sku",
       "external_ref", "product_type", "predefined_product_type", "product_service_type",
       "price_defining_method", "custom_panel", "predefined_panel",
       "measurement_unit_id", "enable_stock_management", "visible", "category_id"]

async def main():
    async with async_session() as db:
        c = (await db.execute(select(Customer).where(Customer.name == "visualgraphx"))).scalars().first()
        auth = OpsAuth(base_url=c.ops_base_url, token_url=c.ops_token_url,
                       client_id=c.ops_client_id, client_secret=c.ops_auth_config["client_secret"])
        # Grab a few of OUR products that were already pushed (have an ops id)
        pushed = (await db.execute(
            select(Product.supplier_sku, Product.ops_product_id)
            .where(Product.ops_product_id.is_not(None)).limit(4)
        )).all()

    targets = [(309, "Custom Pole Flag — known PRINT product")]
    for sku, opid in pushed:
        try:
            targets.append((int(opid), f"OUR push: {sku}"))
        except (TypeError, ValueError):
            pass

    async with OpsGraphQLClient(auth) as client:
        fields = await scalar_fields(client, "ProductsDetails")
        sel = " ".join(fields)
        q = f"query D($id:Int){{ productsDetails(products_id:$id){{ products {{ {sel} }} }} }}"

        for pid, label in targets:
            r = await client.execute(q, variables={"id": pid})
            print(f"=== OPS product {pid}: {label} ===")
            if not r.ok:
                print("  ERR:", r.ops_error_code, r.ops_error_message); print(); continue
            rows = ((r.data or {}).get("productsDetails") or {}).get("products") or []
            if not rows:
                print("  (not found)"); print(); continue
            p = rows[0]
            for k in KEY:
                if k in p and p[k] not in (None, ""):
                    print(f"  {k} = {p[k]!r}")
            print()

        # How are 309's decoration / additional options structured?
        ofields = await scalar_fields(client, "ProductAdditionalOptions")
        osel = " ".join(ofields)
        oq = f"query O($id:Int){{ productAdditionalOptions(products_id:$id){{ productAdditionalOptions {{ {osel} }} totalProductAdditionalOptions }} }}"
        r = await client.execute(oq, variables={"id": 309})
        print("=== OPS product 309 — additional options (decorations/extras) ===")
        if r.ok:
            blk = (r.data or {}).get("productAdditionalOptions") or {}
            print("  total options:", blk.get("totalProductAdditionalOptions"))
            for o in (blk.get("productAdditionalOptions") or [])[:12]:
                show = {k: o.get(k) for k in ("title", "options_type", "options_code", "option_key", "required", "setup_cost", "multiplier") if o.get(k) not in (None, "")}
                print("  -", show)
        else:
            print("  ERR:", r.ops_error_code, r.ops_error_message)

if __name__ == "__main__":
    asyncio.run(main())
