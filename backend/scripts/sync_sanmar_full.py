"""Full SanMar catalog sync — fetches all sellable styles and persists.

Runs N parallel workers (default 4) consuming a shared queue of SKUs.
Each worker uses its own DB session so a failed product doesn't poison
the others. Progress is logged every 10 products.

Run from backend/ with the venv active:
    python scripts/sync_sanmar_full.py

Tunable via env:
    SANMAR_SYNC_WORKERS=4   # parallelism
    SANMAR_SYNC_LIMIT=0     # 0 = no limit; set to N to test on first N styles
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from uuid import UUID

from database import async_session
from modules.catalog.persistence import persist_product
from modules.import_jobs.base import DiscoveryMode, ProductRef
from modules.promostandards.sanmar_adapter import SanMarAdapter
from modules.suppliers.models import Supplier


SANMAR_SUPPLIER_ID = UUID("a73a8445-2f08-4293-9625-b3e480ddc1da")
WORKERS = int(os.getenv("SANMAR_SYNC_WORKERS", "4"))
LIMIT = int(os.getenv("SANMAR_SYNC_LIMIT", "0"))  # 0 == unlimited


class Stats:
    def __init__(self) -> None:
        self.done = 0
        self.failed = 0
        self.failed_skus: list[tuple[str, str]] = []
        self.total = 0
        self.t0 = time.time()

    def log_progress(self) -> None:
        n = self.done + self.failed
        elapsed = time.time() - self.t0
        rate = n / elapsed if elapsed > 0 else 0
        remaining = (self.total - n) / rate if rate > 0 else 0
        print(
            f"  progress: {n}/{self.total}  ok={self.done} failed={self.failed}  "
            f"rate={rate:.1f}/s  eta={remaining/60:.1f} min",
            flush=True,
        )


async def worker(name: str, supplier_id: UUID, queue: asyncio.Queue, stats: Stats) -> None:
    """One concurrent worker; pulls SKUs off the queue and syncs them."""
    while True:
        sku = await queue.get()
        if sku is None:  # sentinel — shutdown signal
            queue.task_done()
            return
        try:
            async with async_session() as db:
                supplier = await db.get(Supplier, supplier_id)
                adapter = SanMarAdapter(supplier=supplier, db=db)
                ingest = await adapter.hydrate_product(ProductRef(supplier_sku=sku))
                await persist_product(db, supplier_id, ingest, category_id=None)
                await db.commit()
            stats.done += 1
        except Exception as exc:  # noqa: BLE001
            stats.failed += 1
            stats.failed_skus.append((sku, f"{type(exc).__name__}: {exc}"))
        finally:
            queue.task_done()
            if (stats.done + stats.failed) % 10 == 0:
                stats.log_progress()


async def main() -> int:
    async with async_session() as db:
        supplier = await db.get(Supplier, SANMAR_SUPPLIER_ID)
        if supplier is None:
            print("ERROR: SanMar supplier missing", file=sys.stderr)
            return 2
        adapter = SanMarAdapter(supplier=supplier, db=db)

    print("Discovering SanMar sellable catalog…", flush=True)
    refs = await adapter.discover(mode=DiscoveryMode.FULL_SELLABLE)
    # discover() returns ProductRef per part — collapse to unique product SKUs
    unique_skus = sorted({ref.supplier_sku for ref in refs})
    if LIMIT:
        unique_skus = unique_skus[:LIMIT]
    print(f"  → {len(unique_skus):,} unique product styles", flush=True)

    stats = Stats()
    stats.total = len(unique_skus)
    queue: asyncio.Queue = asyncio.Queue()
    for sku in unique_skus:
        queue.put_nowait(sku)
    for _ in range(WORKERS):
        queue.put_nowait(None)  # sentinels

    print(f"Starting {WORKERS} workers…\n", flush=True)
    workers = [
        asyncio.create_task(worker(f"w{i}", SANMAR_SUPPLIER_ID, queue, stats))
        for i in range(WORKERS)
    ]
    await queue.join()
    await asyncio.gather(*workers)

    elapsed = time.time() - stats.t0
    print("\n━━━ Summary ━━━")
    print(f"  total elapsed:    {elapsed/60:.1f} min")
    print(f"  succeeded:        {stats.done:,}")
    print(f"  failed:           {stats.failed:,}")
    if stats.failed_skus[:20]:
        print(f"  first 20 failures:")
        for sku, err in stats.failed_skus[:20]:
            print(f"    {sku}: {err[:100]}")
    return 0 if stats.failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
