"""Image mirroring pipeline.

Downloads images from supplier CDNs, resizes + converts to WebP, uploads to S3/R2,
then updates product_images.url to point at our CDN. Keeps supplier_image_url for
provenance.

Entry points:
  mirror_product_images(product_id, db)  — mirror one product (in the caller's session)
  mirror_products_batch(product_ids)     — fire-and-forget across many products
"""

import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from io import BytesIO
from typing import Optional
from uuid import UUID

import httpx
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.images.storage import is_own_cdn, upload_image

log = logging.getLogger(__name__)

# Configurable image processing settings
_MAX_DIM = int(os.getenv("IMAGE_MAX_DIMENSION", "1200"))
_WEBP_Q = int(os.getenv("IMAGE_WEBP_QUALITY", "85"))
# Hard download size cap — prevents a malicious/broken supplier URL from
# streaming multi-GB into process memory.  Default 20 MB.
_MAX_DOWNLOAD_BYTES = int(os.getenv("IMAGE_MAX_DOWNLOAD_BYTES", str(20 * 1024 * 1024)))


# ── helpers ──────────────────────────────────────────────────────────────────

def _slugify(s: str) -> str:
    if not s:
        return "unknown"
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "unknown"


def _s3_key(supplier_slug: str, sku: str, image_type: str, color: Optional[str], checksum: str) -> str:
    """Deterministic, content-addressed key.

    products/{supplier}/{sku}/{image_type}/{color}/{checksum[:16]}.webp
    """
    return (
        f"products/{_slugify(supplier_slug)}/{_slugify(sku)}"
        f"/{_slugify(image_type)}/{_slugify(color or 'all')}"
        f"/{checksum[:16]}.webp"
    )


async def _fetch_and_process(url: str) -> tuple[bytes, str]:
    """Download image, resize to _MAX_DIM, convert to WebP. Returns (bytes, sha256).

    Size-caps the download at _MAX_DOWNLOAD_BYTES to prevent runaway memory
    usage from oversized/adversarial supplier URLs.

    Preserves alpha channel — logos and transparent PNGs are saved as WebP
    with RGBA so the transparency survives the format conversion.
    """
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        async with client.stream("GET", url) as r:
            r.raise_for_status()
            chunks: list[bytes] = []
            received = 0
            async for chunk in r.aiter_bytes(chunk_size=65536):
                received += len(chunk)
                if received > _MAX_DOWNLOAD_BYTES:
                    raise ValueError(
                        f"Image at {url} exceeds size cap "
                        f"({_MAX_DOWNLOAD_BYTES // (1024 * 1024)} MB)"
                    )
                chunks.append(chunk)
            raw = b"".join(chunks)

    checksum = hashlib.sha256(raw).hexdigest()

    img = Image.open(BytesIO(raw))

    # Preserve alpha for formats that carry it (PNG, WebP with alpha, GIF).
    # Converting RGB→RGBA is safe; RGBA WebP fully supported by all modern browsers.
    # Only flatten to RGB when the source is already opaque (no alpha channel).
    if img.mode in ("RGBA", "LA", "PA"):
        img = img.convert("RGBA")
    elif img.mode == "P":
        # Paletted — may have transparency; convert via RGBA to preserve it
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    img.thumbnail((_MAX_DIM, _MAX_DIM), Image.Resampling.LANCZOS)

    out = BytesIO()
    img.save(out, format="WEBP", quality=_WEBP_Q)
    return out.getvalue(), checksum


# ── public API ────────────────────────────────────────────────────────────────

async def mirror_product_images(
    product_id: UUID,
    db: AsyncSession,
) -> dict:
    """Mirror all images for one product. Commits on success.

    Returns a summary dict: {product_id, mirrored, skipped, failed, error?}
    """
    from modules.catalog.models import Product, ProductImage
    from modules.suppliers.models import Supplier

    result = await db.execute(
        select(Product, Supplier)
        .join(Supplier, Product.supplier_id == Supplier.id)
        .where(Product.id == product_id)
    )
    row = result.one_or_none()
    if not row:
        return {"product_id": str(product_id), "error": "not found", "mirrored": 0, "skipped": 0, "failed": 0}

    product, supplier = row

    images_q = await db.execute(
        select(ProductImage).where(ProductImage.product_id == product_id)
    )
    images = list(images_q.scalars().all())

    if not images:
        return {"product_id": str(product_id), "mirrored": 0, "skipped": 0, "failed": 0}

    mirrored = skipped = failed = 0

    for img in images:
        # Source URL: prefer supplier_image_url, fall back to current url
        source_url = img.supplier_image_url or img.url
        if not source_url:
            skipped += 1
            continue

        # Already on our CDN — skip unless supplier_image_url shows a newer source
        if is_own_cdn(img.url) and not img.supplier_image_url:
            skipped += 1
            continue

        try:
            webp_bytes, checksum = await _fetch_and_process(source_url)

            # Content unchanged — skip re-upload
            if img.checksum == checksum and is_own_cdn(img.url):
                skipped += 1
                continue

            key = _s3_key(
                supplier_slug=supplier.slug or supplier.name,
                sku=product.supplier_sku,
                image_type=img.image_type,
                color=img.color,
                checksum=checksum,
            )
            cdn_url = await upload_image(webp_bytes, key)

            # Preserve original supplier URL before overwriting
            if not img.supplier_image_url:
                img.supplier_image_url = img.url

            img.url = cdn_url
            img.checksum = checksum
            img.mirrored_at = datetime.now(timezone.utc)
            mirrored += 1

        except httpx.HTTPError as exc:
            log.warning(
                "Mirror HTTP error [product=%s img=%s]: %s", product_id, source_url, exc
            )
            failed += 1
        except Exception as exc:
            log.warning(
                "Mirror failed [product=%s img=%s]: %s", product_id, source_url, exc
            )
            failed += 1

    now = datetime.now(timezone.utc)
    product.last_image_fetch_at = now
    product.last_image_fetch_attempt_at = now

    # Refresh primary image_url from the best mirrored front image
    front_imgs = sorted(
        [i for i in images if i.image_type == "front" and is_own_cdn(i.url)],
        key=lambda x: x.sort_order,
    )
    if front_imgs:
        product.image_url = front_imgs[0].url
    elif mirrored > 0:
        # Any CDN image is better than a supplier URL
        any_cdn = next((i for i in images if is_own_cdn(i.url)), None)
        if any_cdn:
            product.image_url = any_cdn.url

    await db.commit()

    return {
        "product_id": str(product_id),
        "mirrored": mirrored,
        "skipped": skipped,
        "failed": failed,
    }


async def mirror_products_batch(product_ids: list[UUID]) -> dict:
    """Mirror images for many products, each in its own session.

    Returns aggregate counts. Safe to call from a background task.
    """
    from database import async_session

    total = mirrored = skipped = failed = errors = 0
    for pid in product_ids:
        total += 1
        try:
            async with async_session() as db:
                res = await mirror_product_images(pid, db)
            mirrored += res.get("mirrored", 0)
            skipped += res.get("skipped", 0)
            failed += res.get("failed", 0)
        except Exception as exc:
            log.error("Batch mirror error for product %s: %s", pid, exc)
            errors += 1

    log.info(
        "Batch mirror complete: total=%d mirrored=%d skipped=%d failed=%d errors=%d",
        total, mirrored, skipped, failed, errors,
    )
    return {"total": total, "mirrored": mirrored, "skipped": skipped, "failed": failed, "errors": errors}
