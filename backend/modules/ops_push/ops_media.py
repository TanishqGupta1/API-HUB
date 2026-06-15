"""Stage product images into OPS's own media storage.

OPS's setProductsImageGallery mutation does NOT fetch external URLs — it
treats ``products_large_image_name`` as a bare filename inside its media
folder and prepends its CDN path to whatever string it receives. Sending a
full URL produces a broken concatenated path (verified live 2026-06-12 on
staging product 584: ``https://<ops-cdn>/.../products_gallery_images/https://<our-cdn>/...``).

The OPS media folder lives in the same shared S3 bucket we mirror images to
(e.g. staging: ``ctmediaon_staging/images/products_gallery_images/``), so
"staging an image for OPS" means copying the already-mirrored WebP to that
prefix — as a ``<name>.webp`` + ``<name>_thumb.webp`` pair, matching what the
OPS admin upload UI produces — and sending just the filename in the mutation.

Config:
  OPS_MEDIA_IMAGE_PREFIX         — S3 key prefix of the OPS gallery media folder
                                   (unset = gallery staging disabled)
  OPS_MEDIA_PRODUCT_IMAGE_PREFIX — S3 key prefix of the OPS product image folder
                                   used by setProduct.imagename (unset = disabled)
  OPS_MEDIA_THUMB_DIMENSION      — thumb max dimension in px (default 300)
"""

import logging
import os
from io import BytesIO
from typing import Optional

from PIL import Image

from modules.images.storage import (
    CDN_BASE_URL,
    get_object_bytes,
    get_object_size,
    is_own_cdn,
    key_exists,
    upload_image,
)

# Minimum source size (bytes) to be eligible for the OPS gallery.
# SanMar's per-color "swatch chip" images are ~60-100b solid-color squares;
# real product photos are kilobytes to megabytes. 1KB is a comfortable cut.
MIN_GALLERY_IMAGE_BYTES = 1024

log = logging.getLogger(__name__)


def media_prefix() -> str:
    """The OPS gallery media folder prefix, or "" when staging is disabled."""
    return os.getenv("OPS_MEDIA_IMAGE_PREFIX", "").strip().strip("/")


def product_media_prefix() -> str:
    """The OPS product image folder prefix (setProduct.imagename), or "" when disabled."""
    return os.getenv("OPS_MEDIA_PRODUCT_IMAGE_PREFIX", "").strip().strip("/")


def _filename_for(sku: str, source_key: str) -> str:
    """Deterministic OPS media filename: ``<sku>_<checksum>.webp``.

    The checksum comes from the mirror's content-addressed key, so a re-push
    of unchanged content overwrites the same file instead of accumulating
    duplicates in the (flat) OPS media folder.
    """
    checksum = source_key.rsplit("/", 1)[-1].removesuffix(".webp")
    safe_sku = "".join(c if c.isalnum() else "_" for c in sku.lower())
    return f"{safe_sku}_{checksum}.webp"


async def stage_image_for_ops(image_url: str, sku: str) -> Optional[str]:
    """Copy a mirrored image into the OPS media folder. Returns the bare filename.

    Only operates on images already mirrored to our CDN (same bucket); returns
    None for supplier URLs, unconfigured prefix, or any failure — callers
    treat None as "cannot be pushed to the gallery".
    """
    prefix = media_prefix()
    if not prefix or not is_own_cdn(image_url):
        return None

    source_key = image_url[len(CDN_BASE_URL) + 1 :]

    # Reject tiny images — they're per-color swatch chips, not product photos.
    source_size = await get_object_size(source_key)
    if source_size is not None and source_size < MIN_GALLERY_IMAGE_BYTES:
        return None

    filename = _filename_for(sku, source_key)
    base = filename.removesuffix(".webp")
    large_key = f"{prefix}/{filename}"
    thumb_key = f"{prefix}/{base}_thumb.webp"

    if await key_exists(large_key) and await key_exists(thumb_key):
        return filename

    data = await get_object_bytes(source_key)
    if not data:
        log.warning("OPS media staging: source object missing for %s", source_key)
        return None

    await upload_image(data, large_key)

    thumb_dim = int(os.getenv("OPS_MEDIA_THUMB_DIMENSION", "300"))
    img = Image.open(BytesIO(data))
    img.thumbnail((thumb_dim, thumb_dim), Image.Resampling.LANCZOS)
    out = BytesIO()
    img.save(out, format="WEBP", quality=80)
    await upload_image(out.getvalue(), thumb_key)

    return filename


async def stage_product_image_for_ops(image_url: str, sku: str) -> Optional[str]:
    """Copy a mirrored image into the OPS product image folder. Returns the bare filename.

    Unlike gallery staging (which produces large+thumb pairs), this uploads a
    single file to the ``product/`` folder used by ``setProduct.imagename``.
    OPS prepends its CDN path to that field to build the product description
    small-image URL.
    """
    prefix = product_media_prefix()
    if not prefix or not is_own_cdn(image_url):
        return None

    source_key = image_url[len(CDN_BASE_URL) + 1:]
    filename = _filename_for(sku, source_key)
    dest_key = f"{prefix}/{filename}"

    if await key_exists(dest_key):
        return filename

    data = await get_object_bytes(source_key)
    if not data:
        log.warning("OPS product image staging: source object missing for %s", source_key)
        return None

    await upload_image(data, dest_key)
    return filename
