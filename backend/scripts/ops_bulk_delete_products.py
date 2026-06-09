"""Bulk-delete OPS products created during API-HUB testing (Phase 7).

OPS has no `deleteProduct` mutation. Deletion is via `setProduct` with
`delete: 1` — same pattern as AdditionalOptionInput's `delete` field.

This script:
  1. Calls setProduct(delete=1) for each given OPS products_id.
  2. Deletes the matching push_mappings rows from our DB (and their
     push_mapping_options children) so a fresh re-push runs as `create`
     instead of `update`.

Usage:
    cd backend && source .venv/bin/activate
    OPS_PRODUCT_IDS=548,549,551,552,553,554,555,556 \
        python scripts/ops_bulk_delete_products.py

Or pass `--dry-run` to see what would be deleted without calling OPS:
    OPS_PRODUCT_IDS=548,549 python scripts/ops_bulk_delete_products.py --dry-run
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

from sqlalchemy import delete, select

sys.path.append(os.getcwd())

from database import async_session  # noqa: E402
from modules.customers.models import Customer  # noqa: E402
from modules.ops_client.client import OpsAuth, OpsGraphQLClient  # noqa: E402
from modules.push_mappings.models import PushMapping, PushMappingOption  # noqa: E402


CUSTOMER_NAME_DEFAULT = "visualgraphx"

# Same mutation string as modules/ops_client/mutations.py uses (kept inline
# to avoid an import cycle through arrays-vs-single shape differences).
_SET_PRODUCT = """
mutation SetProductDelete($inputs: [ProductInput!]!) {
  setProduct(inputs: $inputs) {
    result
    message
    id
  }
}
""".strip()


async def _load_client(customer_name: str) -> OpsGraphQLClient:
    async with async_session() as db:
        cust = (await db.execute(
            select(Customer).where(Customer.name == customer_name)
        )).scalar_one_or_none()
    if cust is None:
        raise SystemExit(f"Customer {customer_name!r} not found in DB.")
    secret = (cust.ops_auth_config or {}).get("client_secret")
    if not secret:
        raise SystemExit(f"Customer {customer_name!r} has no client_secret.")
    return OpsGraphQLClient(OpsAuth(
        base_url=cust.ops_base_url,
        token_url=cust.ops_token_url,
        client_id=cust.ops_client_id,
        client_secret=secret,
    ))


async def _delete_one(client: OpsGraphQLClient, product_id: int) -> tuple[bool, str]:
    """Call setProduct(delete=1). Returns (ok, message)."""
    payload = {"inputs": [{"products_id": product_id, "delete": 1}]}
    r = await client.execute(_SET_PRODUCT, variables=payload)
    if not r.ok:
        return False, r.ops_error_message or "unknown OPS error"
    data = (r.data or {}).get("setProduct")
    # OPS returns a list of {result, message, id} (mirrors array input).
    row = data[0] if isinstance(data, list) and data else data
    if not isinstance(row, dict):
        return False, f"unexpected response shape: {data!r}"
    if row.get("result") is False:
        return False, row.get("message") or "OPS rejected delete"
    return True, row.get("message") or "ok"


async def _clear_local_mappings(product_ids: list[int]) -> int:
    async with async_session() as db:
        mapping_ids = (await db.execute(
            select(PushMapping.id).where(
                PushMapping.target_ops_product_id.in_(product_ids)
            )
        )).scalars().all()
        if not mapping_ids:
            return 0
        await db.execute(
            delete(PushMappingOption).where(
                PushMappingOption.push_mapping_id.in_(mapping_ids)
            )
        )
        await db.execute(
            delete(PushMapping).where(PushMapping.id.in_(mapping_ids))
        )
        await db.commit()
        return len(mapping_ids)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be deleted without touching OPS or the DB.",
    )
    ap.add_argument(
        "--customer", default=CUSTOMER_NAME_DEFAULT,
        help=f"Customer name (default: {CUSTOMER_NAME_DEFAULT!r}).",
    )
    args = ap.parse_args()

    raw = os.getenv("OPS_PRODUCT_IDS", "").strip()
    if not raw:
        ap.error("OPS_PRODUCT_IDS env var is required (comma-separated ints).")
    try:
        product_ids = [int(x.strip()) for x in raw.split(",") if x.strip()]
    except ValueError as e:
        ap.error(f"OPS_PRODUCT_IDS must be a comma-separated list of ints: {e}")
    if not product_ids:
        ap.error("OPS_PRODUCT_IDS resolved to empty list.")

    print(f"Customer: {args.customer}")
    print(f"Targets:  {product_ids}")
    print(f"Mode:     {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print()

    if args.dry_run:
        print("Dry-run — would call setProduct(delete=1) for each ID above.")
        return 0

    client = await _load_client(args.customer)
    try:
        ok = 0
        fail = 0
        for pid in product_ids:
            success, msg = await _delete_one(client, pid)
            mark = "✓" if success else "✗"
            print(f"  {mark} {pid}: {msg}")
            if success:
                ok += 1
            else:
                fail += 1
        print()
        print(f"OPS: {ok} deleted, {fail} failed.")
    finally:
        await client.aclose()

    cleared = await _clear_local_mappings(product_ids)
    print(f"DB:  cleared {cleared} push_mapping row(s).")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
