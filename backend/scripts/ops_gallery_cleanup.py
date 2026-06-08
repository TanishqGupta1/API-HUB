"""Delete the broken/test gallery rows we created on a product (#547)."""
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

_READ = """
query($id: Int!){ productsImageGallery(products_id:$id){
  productsImageGallery { products_image_gallery_id products_large_image_name } } }
""".strip()
_DEL = """
mutation M($products_id: Int!, $input: ProductsImageGalleryBulkInput!) {
  setProductsImageGallery(products_id: $products_id, input: $input) { result message }
}
""".strip()


async def main():
    async with async_session() as db:
        cust = (await db.execute(select(Customer).where(Customer.id == CUSTOMER_ID))).scalar_one()
    client = OpsGraphQLClient(OpsAuth(
        base_url=cust.ops_base_url, token_url=cust.ops_token_url,
        client_id=cust.ops_client_id,
        client_secret=(cust.ops_auth_config or {}).get("client_secret"),
    ))
    r = await client.execute(_READ, variables={"id": PRODUCT_ID})
    rows = (r.data or {}).get("productsImageGallery", {}).get("productsImageGallery", []) or []
    ids = [row["products_image_gallery_id"] for row in rows]
    print(f"gallery rows on #{PRODUCT_ID}: {ids}")
    if not ids:
        print("nothing to delete")
        return
    image_arr = [{"products_image_gallery_id": gid, "delete": 1, "status": "1"} for gid in ids]
    d = await client.execute(_DEL, variables={"products_id": PRODUCT_ID, "input": {"image_arr": image_arr}})
    print("delete resp:", json.dumps(d.data) if d.ok else d.ops_error_message)
    r2 = await client.execute(_READ, variables={"id": PRODUCT_ID})
    left = [row["products_image_gallery_id"] for row in
            (r2.data or {}).get("productsImageGallery", {}).get("productsImageGallery", [])]
    print(f"remaining rows: {left}")


if __name__ == "__main__":
    asyncio.run(main())
