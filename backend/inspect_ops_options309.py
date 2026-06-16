"""Read-only: learn how a working PRINT product (309) models its additional
options + attributes, so we can reproduce embroidery/decoration options.
Run: python inspect_ops_options309.py
"""
from __future__ import annotations
import asyncio, json
from sqlalchemy import select
from database import async_session
from modules.customers.models import Customer
from modules.ops_client.client import OpsAuth, OpsGraphQLClient

_TYPE = """query T($name:String!){ __type(name:$name){ name kind
  fields{ name type{kind name ofType{kind name ofType{kind name}}} } } }"""

def _base(t):
    while t and t.get("ofType"):
        t = t["ofType"]
    return t or {}

async def readable_fields(client, typename):
    """Scalar field names (skip object/list fields that need sub-selections)."""
    r = await client.execute(_TYPE, variables={"name": typename})
    t = (r.data or {}).get("__type") or {}
    scal, objs = [], []
    for f in t.get("fields") or []:
        bt = _base(f["type"])
        if bt.get("kind") == "SCALAR" or bt.get("name") in {"String", "Int", "Float", "Boolean", "ID"}:
            scal.append(f["name"])
        else:
            objs.append((f["name"], bt.get("name")))
    return scal, objs

async def main():
    async with async_session() as db:
        c = (await db.execute(select(Customer).where(Customer.name == "visualgraphx"))).scalars().first()
        auth = OpsAuth(base_url=c.ops_base_url, token_url=c.ops_token_url,
                       client_id=c.ops_client_id, client_secret=c.ops_auth_config["client_secret"])

    async with OpsGraphQLClient(auth) as client:
        scal, objs = await readable_fields(client, "ProductAdditionalOptions")
        print("ProductAdditionalOptions scalar fields:", scal)
        print("ProductAdditionalOptions object fields:", objs, "\n")

        # Curated, low-risk subset (the ones we care about for decorations)
        want = [f for f in ("prod_add_opt_id", "title", "description", "options_type",
                            "options_code", "option_key", "required", "status",
                            "price_calculate_type", "applicable_for", "apply_multiplication",
                            "multiplier_type", "multiplier", "setup_cost", "master_option_id",
                            "prod_add_opt_group_id") if f in scal]
        sel = " ".join(want)
        q = f"query O($id:Int){{ productAdditionalOptions(products_id:$id){{ productAdditionalOptions {{ {sel} }} totalProductAdditionalOptions }} }}"
        r = await client.execute(q, variables={"id": 309})
        print("=== product 309 additional options ===")
        if not r.ok:
            print("  ERR:", r.ops_error_code, r.ops_error_message)
        else:
            blk = (r.data or {}).get("productAdditionalOptions") or {}
            print("  total:", blk.get("totalProductAdditionalOptions"))
            for o in (blk.get("productAdditionalOptions") or []):
                print("  -", json.dumps({k: v for k, v in o.items() if v not in (None, "")}, default=str))

        # And the attributes (the choices within each option, e.g. Embroidery / Screen Print)
        ascal, _ = await readable_fields(client, "ProductsAttribute")
        print("\nProductsAttribute scalar fields:", ascal)

if __name__ == "__main__":
    asyncio.run(main())
