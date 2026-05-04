import asyncio
import logging
import argparse
from sqlalchemy import select
from database import async_session
from modules.catalog.models import Product
from modules.images.service import trigger_lazy_image_fetch

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("sync_images")

async def sync_all_images(limit: int = 100):
    """
    Syncs images for N products that currently have no images.
    """
    async with async_session() as session:
        # Find products with no images
        # We use a join check or any() to find products lacking ProductImage records
        from modules.catalog.models import ProductImage
        stmt = (
            select(Product)
            .outerjoin(ProductImage)
            .where(ProductImage.id == None)
            .limit(limit)
        )
        result = await session.execute(stmt)
        products = result.scalars().all()
        
        log.info(f"Found {len(products)} products needing image sync (limit={limit})")
        
        for prod in products:
            log.info(f"Syncing images for {prod.supplier_sku}...")
            try:
                await trigger_lazy_image_fetch(prod.id, prod.supplier_id)
            except Exception as e:
                log.error(f"Failed to sync {prod.supplier_sku}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    
    asyncio.run(sync_all_images(limit=args.limit))
