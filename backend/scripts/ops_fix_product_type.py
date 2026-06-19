"""One-off: set product_type="15" on an existing OPS product (Add to cart / stock apparel).

Per the live OPS legend: 1=Custom Design, 2=Upload Center, 3=Browse Design,
7=Quote, 8=Hire Designer, 15=Add to cart. Stock apparel products must be "15".

Usage (from backend/):
    python scripts/ops_fix_product_type.py --product-id 603
    python scripts/ops_fix_product_type.py --product-id 603 --dry-run
    python scripts/ops_fix_product_type.py --product-id 603 --base-url https://staging.visualgraphx.com
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import select

sys.path.append(os.getcwd())

from database import async_session  # noqa: E402
from modules.customers.models import Customer  # noqa: E402
from modules.ops_client.client import OpsAuth, OpsGraphQLClient  # noqa: E402

_SET_PRODUCT = """
mutation SetProductType($inputs: [ProductInput!]!) {
  setProduct(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


async def _load_client(base_url: str | None) -> OpsGraphQLClient:
    async with async_session() as db:
        query = select(Customer).where(Customer.is_active.is_(True))
        if base_url:
            query = query.where(Customer.ops_base_url == base_url)
        cust = (await db.execute(query)).scalars().first()
    if cust is None:
        hint = f" with ops_base_url={base_url!r}" if base_url else " (active)"
        raise SystemExit(f"No customer{hint} found in DB.")
    secret = (cust.ops_auth_config or {}).get("client_secret")
    if not secret:
        raise SystemExit(f"Customer {cust.name!r} has no client_secret.")
    return OpsGraphQLClient(OpsAuth(
        base_url=cust.ops_base_url,
        token_url=cust.ops_token_url,
        client_id=cust.ops_client_id,
        client_secret=secret,
    ))


async def main(product_id: int, dry_run: bool, base_url: str | None) -> None:
    print(f"Target: products_id={product_id}, product_type='15'")
    if dry_run:
        print("[dry-run] Would call setProduct — skipping.")
        return

    client = await _load_client(base_url)
    payload = {"inputs": [{"products_id": product_id, "product_type": "15"}]}
    r = await client.execute(_SET_PRODUCT, variables=payload)

    if not r.ok:
        print(f"ERROR: {r.ops_error_message or 'unknown OPS error'}")
        sys.exit(1)

    data = (r.data or {}).get("setProduct")
    row = data[0] if isinstance(data, list) and data else data
    if isinstance(row, dict) and row.get("result") is False:
        print(f"OPS rejected: {row.get('message')}")
        sys.exit(1)

    print(f"OK: {row}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-id", type=int, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--base-url", default=None, help="OPS base URL; uses first active customer if omitted")
    args = parser.parse_args()
    asyncio.run(main(args.product_id, args.dry_run, args.base_url))
