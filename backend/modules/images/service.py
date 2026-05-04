import hashlib
import httpx
import logging
import os
from typing import Optional
from uuid import UUID

log = logging.getLogger(__name__)

# Configurable via environment variables
S3_BUCKET = os.getenv("S3_PRODUCT_IMAGES_BUCKET", "product-images-dev")
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "https://cdn.example.com")

async def fetch_and_store_image(
    image_url: str, 
    supplier: str, 
    product_id: str, 
    color: str, 
    image_type: str,
    filename: str
) -> tuple[str, str]:
    """
    Downloads an image, generates a checksum, uploads to S3, and returns (cdn_url, checksum).
    
    Path structure: {supplier}/{product_id}/{color}/{image_type}/{filename}
    """
    # 1. Download image
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(image_url, timeout=30.0)
            response.raise_for_status()
            image_data = response.content
        except Exception as e:
            log.error(f"Failed to download image from {image_url}: {e}")
            raise

    # 2. Generate checksum (SHA-256)
    checksum = hashlib.sha256(image_data).hexdigest()

    # 3. Check if already exists in S3 (mocked for now)
    # key = f"{supplier}/{product_id}/{color}/{image_type}/{filename}"
    # if await s3_client.exists(S3_BUCKET, key):
    #     return f"{CDN_BASE_URL}/{key}", checksum

    # 4. Upload to S3 (mocked for now)
    cdn_url = await _mock_upload_to_s3(image_data, supplier, product_id, color, image_type, filename)
    
    return cdn_url, checksum

async def _mock_upload_to_s3(
    image_data: bytes, 
    supplier: str, 
    product_id: str, 
    color: str, 
    image_type: str,
    filename: str
) -> str:
    """
    Mocked S3 upload that returns a predictable CDN URL.
    """
    # Normalize path components
    supplier = supplier.lower()
    product_id = product_id.upper()
    color = color.lower().replace(" ", "_")
    image_type = image_type.lower()
    
    key = f"{supplier}/{product_id}/{color}/{image_type}/{filename}"
    log.info(f"MOCK: Uploaded {len(image_data)} bytes to s3://{S3_BUCKET}/{key}")
    
    return f"{CDN_BASE_URL}/{key}"

async def trigger_lazy_image_fetch(product_id: UUID, supplier_id: UUID):
    """
    Background job to fetch images for a product from SanMar FTP.
    """
    from sqlalchemy import select
    from database import async_session
    from modules.catalog.models import Product, ProductImage
    from modules.suppliers.models import Supplier
    from modules.images.sanmar_ftp import SanMarFTPClient, map_sanmar_type
    
    async with async_session() as session:
        product = await session.get(Product, product_id)
        supplier = await session.get(Supplier, supplier_id)
        if not product or not supplier:
            return

        # Mock FTP credentials
        ftp = SanMarFTPClient(host="ftp.sanmar.com", user="mock", password="mock")
        
        # In a real scenario, we'd search for the specific style directory
        # For this phase, we'll simulate finding matching images
        all_images = await ftp.list_images()
        matches = [img for img in all_images if img["style"].upper() == product.supplier_sku.upper()]
        
        from datetime import datetime, timezone
        if not matches:
            log.info(f"No SanMar FTP images found for style {product.supplier_sku}")
            product.last_image_fetch_at = datetime.now(timezone.utc)
            await session.commit()
            return

        for match in matches:
            try:
                # Scalability Check: Skip if this specific source URL has already been ingested
                existing_res = await session.execute(
                    select(ProductImage).where(ProductImage.supplier_image_url == match["url"])
                )
                if existing_res.scalar_one_or_none():
                    log.debug(f"Skipping already ingested image: {match['filename']}")
                    continue

                # 1. Fetch and store
                cdn_url, checksum = await fetch_and_store_image(
                    image_url=match["url"],
                    supplier="sanmar",
                    product_id=product.supplier_sku,
                    color=match["color"],
                    image_type=map_sanmar_type(match["type"]),
                    filename=match["filename"]
                )
                
                # 2. Save to DB
                new_img = ProductImage(
                    product_id=product.id,
                    url=cdn_url,
                    supplier_image_url=match["url"],
                    image_type=map_sanmar_type(match["type"]),
                    color=match["color"],
                    checksum=checksum
                )
                session.add(new_img)
            except Exception as e:
                log.error(f"Lazy fetch failed for {match['filename']}: {e}")

        product.last_image_fetch_at = datetime.now(timezone.utc)
        await session.commit()
        log.info(f"Successfully lazy-fetched {len(matches)} images for product {product.supplier_sku}")
