"""Read back what OPS actually stored for a product's images.

Introspects the `products` query + Product output type for image fields, then
fetches product #547 to see whether OPS fetched the gallery URL or just stored
the string (and what the main `imagename` holds).
"""
import asyncio
import json
import os
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.append(os.getcwd())

from database import async_session  # noqa: E402
from modules.customers.models import Customer  # noqa: E402
from modules.ops_client.client import OpsAuth, OpsGraphQLClient  # noqa: E402

CUSTOMER_ID = os.getenv("OPS_SPIKE_CUSTOMER_ID", "8eb1d4f2-6cd3-4129-a7dd-066aacba2064")
PRODUCT_ID = int(os.getenv("OPS_SPIKE_PRODUCT_ID", "547"))

_INTROSPECT = """
query I($name: String!) {
  __type(name: $name) {
    name kind
    fields { name type { name kind ofType { name kind ofType { name kind } } } }
  }
}
""".strip()

_LIST_QUERIES = """
query { __schema { queryType { fields { name args { name type { name kind ofType { name kind } } } } } } }
""".strip()


def _ts(t):
    if not t:
        return "?"
    if t.get("kind") == "NON_NULL":
        return _ts(t.get("ofType")) + "!"
    if t.get("kind") == "LIST":
        return "[" + _ts(t.get("ofType")) + "]"
    return t.get("name") or "?"


async def _client(db: AsyncSession) -> OpsGraphQLClient:
    cust = (await db.execute(select(Customer).where(Customer.id == CUSTOMER_ID))).scalar_one()
    return OpsGraphQLClient(OpsAuth(
        base_url=cust.ops_base_url, token_url=cust.ops_token_url,
        client_id=cust.ops_client_id,
        client_secret=(cust.ops_auth_config or {}).get("client_secret"),
    ))


async def introspect(client, name):
    print(f"\n=== {name} fields ===")
    r = await client.execute(_INTROSPECT, variables={"name": name})
    if not r.ok:
        print("  ERR:", r.ops_error_code, r.ops_error_message); return
    t = (r.data or {}).get("__type")
    if not t:
        print("  (not found)"); return
    for f in t.get("fields") or []:
        if any(k in f["name"].lower() for k in ("image", "gallery", "photo", "media", "thumb", "pic")):
            print(f"    {f['name']}: {_ts(f['type'])}")


async def list_product_queries(client):
    print("\n=== queries matching product ===")
    r = await client.execute(_LIST_QUERIES, variables={})
    if not r.ok:
        print("  ERR:", r.ops_error_code, r.ops_error_message); return
    fields = (((r.data or {}).get("__schema") or {}).get("queryType") or {}).get("fields") or []
    for f in fields:
        if "product" in f["name"].lower():
            args = ", ".join(f"{a['name']}: {_ts(a['type'])}" for a in f.get("args") or [])
            print(f"    {f['name']}({args})")


async def main():
    async with async_session() as db:
        client = await _client(db)
    await list_product_queries(client)
    for tn in ("ProductsData", "ProductsImageGalleryData", "ProductsDetailsData"):
        await introspect_all(client, tn)

    print(f"\n=== read back product {PRODUCT_ID} ===")
    queries = {
        "gallery":
            "query($id: Int!){ productsImageGallery(products_id:$id){ productsImageGallery { products_image_gallery_id products_large_image_name products_thumb_image_name } totalProductsImageGallery } }",
        "details":
            "query($id: Int!){ productsDetails(products_id:$id){ products { products_id imagename } } }",
    }
    for label, q in queries.items():
        r = await client.execute(q, variables={"id": PRODUCT_ID})
        print(f"  [{label}] ok={r.ok} "
              + (f"data={json.dumps(r.data)[:600]}" if r.ok else f"err={r.ops_error_message}"))


async def introspect_all(client, name):
    """Introspect ALL fields of a type (not just image-named ones)."""
    print(f"\n=== {name} (all fields) ===")
    r = await client.execute(_INTROSPECT, variables={"name": name})
    if not r.ok:
        print("  ERR:", r.ops_error_code, r.ops_error_message); return
    t = (r.data or {}).get("__type")
    if not t:
        print("  (not found)"); return
    for f in t.get("fields") or []:
        print(f"    {f['name']}: {_ts(f['type'])}")


if __name__ == "__main__":
    asyncio.run(main())
