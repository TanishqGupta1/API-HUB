"""Read-only deep-dive: real shapes of the design / decoration mutations, and
the readable fields of the product-detail queries. Follows inspect_ops_schema.py.
Never mutates. Run: python inspect_ops_design.py
"""
from __future__ import annotations
import asyncio
from sqlalchemy import select
from database import async_session
from modules.customers.models import Customer
from modules.ops_client.client import OpsAuth, OpsGraphQLClient

_ROOT = """
query {
  __schema {
    mutationType { fields { name args { name type { kind name ofType { kind name ofType { kind name } } } } } }
    queryType { fields { name args { name type { kind name ofType { kind name ofType { kind name } } } }
                         type { kind name ofType { kind name } } } }
  }
}
""".strip()

_TYPE = """
query T($name:String!){ __type(name:$name){ name kind
  inputFields{ name type{kind name ofType{kind name ofType{kind name ofType{kind name}}}} }
  fields{ name type{kind name ofType{kind name ofType{kind name}}} } } }
""".strip()

def tstr(t):
    if not t: return "?"
    k, n, o = t.get("kind"), t.get("name"), t.get("ofType")
    if k == "NON_NULL": return tstr(o) + "!"
    if k == "LIST": return "[" + tstr(o) + "]"
    return n or "?"

def base_name(t):
    """Innermost named type, stripping LIST/NON_NULL wrappers."""
    while t and t.get("ofType"):
        t = t["ofType"]
    return t.get("name") if t else None

INTEREST_M = {"setProductDesign", "setProductPages", "setProductSku", "setAdditionalOption", "setProductSize"}
INTEREST_Q = {"productsDetails", "products", "productSize", "productAdditionalOptions"}

async def main():
    async with async_session() as db:
        c = (await db.execute(select(Customer).where(Customer.name == "visualgraphx"))).scalars().first()
        auth = OpsAuth(base_url=c.ops_base_url, token_url=c.ops_token_url,
                       client_id=c.ops_client_id, client_secret=c.ops_auth_config["client_secret"])

    async with OpsGraphQLClient(auth) as client:
        r = await client.execute(_ROOT, variables={})
        if not r.ok:
            print("introspection failed:", r.ops_error_code, r.ops_error_message); return
        muts = r.data["__schema"]["mutationType"]["fields"]
        qs = r.data["__schema"]["queryType"]["fields"]

        input_types, return_types = set(), set()
        print("### MUTATION signatures")
        for f in muts:
            if f["name"] in INTEREST_M:
                sig = ", ".join(f"{a['name']}: {tstr(a['type'])}" for a in f["args"])
                print(f"  {f['name']}({sig})")
                for a in f["args"]:
                    bn = base_name(a["type"])
                    if bn and "Input" in bn: input_types.add(bn)
        print("\n### QUERY signatures (+ return type)")
        for f in qs:
            if f["name"] in INTEREST_Q:
                sig = ", ".join(f"{a['name']}: {tstr(a['type'])}" for a in f["args"])
                rt = base_name(f["type"])
                print(f"  {f['name']}({sig}) -> {rt}")
                if rt: return_types.add(rt)

        print("\n### DESIGN / DECORATION input types")
        for tn in sorted(input_types):
            tr = await client.execute(_TYPE, variables={"name": tn})
            t = (tr.data or {}).get("__type")
            if not t: continue
            flds = t.get("inputFields") or []
            print(f"\n## {tn} ({len(flds)})")
            for fld in flds:
                print(f"  - {fld['name']}: {tstr(fld['type'])}")

        print("\n### PRODUCT-DETAIL return types (readable fields)")
        for tn in sorted(return_types):
            tr = await client.execute(_TYPE, variables={"name": tn})
            t = (tr.data or {}).get("__type")
            if not t: continue
            flds = t.get("fields") or []
            print(f"\n## {tn} ({len(flds)})")
            for fld in flds:
                print(f"  - {fld['name']}: {tstr(fld['type'])}")

if __name__ == "__main__":
    asyncio.run(main())
