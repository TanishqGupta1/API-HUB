"""Retry-sync a small list of specific SanMar SKUs.

Used to pick up the handful that hit transient network timeouts during
the full catalog sync. Same pipeline as the full sync — just a fixed
list of SKUs and 1 worker (so we don't hammer SanMar after it just
timed out on us).

Run from backend/ with the venv active:
    python scripts/retry_sanmar_failed.py
"""
from __future__ import annotations

import asyncio
import sys
from uuid import UUID

from database import async_session
from modules.catalog.persistence import persist_product
from modules.import_jobs.base import ProductRef
from modules.promostandards.sanmar_adapter import SanMarAdapter
from modules.suppliers.models import Supplier


SANMAR_SUPPLIER_ID = UUID("a73a8445-2f08-4293-9625-b3e480ddc1da")
SKUS_TO_RETRY = ["AL2014", "EB559", "F236", "F906", "NEA141", "NL9301"]


async def sync_one(supplier_id: UUID, sku: str) -> tuple[bool, str]:
    try:
        async with async_session() as db:
            supplier = await db.get(Supplier, supplier_id)
            adapter = SanMarAdapter(supplier=supplier, db=db)
            ingest = await adapter.hydrate_product(ProductRef(supplier_sku=sku))
            await persist_product(db, supplier_id, ingest, category_id=None)
            await db.commit()
        return True, f"{len(ingest.variants)} variants"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


async def main() -> int:
    async with async_session() as setup_db:
        supplier = await setup_db.get(Supplier, SANMAR_SUPPLIER_ID)
        if supplier is None:
            print("ERROR: SanMar supplier missing", file=sys.stderr)
            return 2

    print(f"Retrying {len(SKUS_TO_RETRY)} previously-failed SanMar styles…\n")
    succeeded, failed = 0, 0
    for sku in SKUS_TO_RETRY:
        print(f"━━━ {sku} ━━━")
        ok, msg = await sync_one(SANMAR_SUPPLIER_ID, sku)
        if ok:
            succeeded += 1
            print(f"  ✓ {msg}")
        else:
            failed += 1
            print(f"  ✗ {msg[:120]}")
        print()

    print("━━━ Summary ━━━")
    print(f"  succeeded: {succeeded}")
    print(f"  failed:    {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
