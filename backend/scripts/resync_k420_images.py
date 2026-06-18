"""Re-sync K420 from SanMar — fetches product detail + media images and persists.

Addresses the gallery gap: K420 was in the DB with only 1 image (the main product
image) because the per-color media fetch was never completed. This re-hydrates K420
end-to-end so all per-color images land in product_images.

Run from backend/ with the venv active:
    python scripts/resync_k420_images.py
"""
import asyncio
import sys
import os
from uuid import UUID

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func

from database import async_session
from modules.catalog.models import Product, ProductImage
from modules.catalog.persistence import persist_product
from modules.import_jobs.base import ProductRef
from modules.promostandards.sanmar_adapter import SanMarAdapter
from modules.suppliers.models import Supplier

SANMAR_SUPPLIER_ID = UUID("0c5c0dfc-0513-48ba-a5ef-8008df4f39e2")
SKU = "K420"


async def main() -> int:
    async with async_session() as setup_db:
        supplier = await setup_db.get(Supplier, SANMAR_SUPPLIER_ID)
        if supplier is None:
            print("ERROR: SanMar supplier not found", file=sys.stderr)
            return 2

    print(f"Re-syncing {SKU} from SanMar (product + pricing + media + inventory)...")

    async with async_session() as db:
        local_supplier = await db.get(Supplier, supplier.id)
        adapter = SanMarAdapter(supplier=local_supplier, db=db)
        ref = ProductRef(supplier_sku=SKU)
        ingest = await adapter.hydrate_product(ref)

        print(f"  Fetched: {len(ingest.variants)} variants, {len(ingest.images or [])} images")

        await persist_product(db, supplier.id, ingest, category_id=None)
        await db.commit()

    # Verify DB state after persist
    async with async_session() as verify_db:
        product = (await verify_db.execute(
            select(Product).where(
                Product.supplier_sku == SKU,
                Product.supplier_id == SANMAR_SUPPLIER_ID,
            )
        )).scalar_one_or_none()

        if not product:
            print("ERROR: K420 not found in DB after sync", file=sys.stderr)
            return 1

        img_count = (await verify_db.execute(
            select(func.count()).select_from(ProductImage).where(ProductImage.product_id == product.id)
        )).scalar()

        print(f"\nDB after sync:")
        print(f"  Product id : {product.id}")
        print(f"  Images     : {img_count}")

    if img_count > 1:
        print(f"\nSuccess — K420 now has {img_count} images. Re-push to populate gallery.")
    else:
        print(f"\nWarning — still only {img_count} image(s). SanMar may not have per-color media for K420.")

    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
