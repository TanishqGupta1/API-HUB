"""Upload product images to the OPS S3 bucket before pushing to OPS API.

Christian confirmed (2026-06-15 team call) that the correct approach is:
  1. Upload images directly to the OPS S3 bucket under the designated folders.
  2. Pass only the bare filename in setProduct (imagename / product_desc_image)
     and setProductsImageGallery — OPS resolves the file from the known folder.

S3 folder layout (bucket = S3_PRODUCT_IMAGES_BUCKET, default "ctmediaimg"):
  {prefix}/images/product/                    ← imagename / product_desc_image
  {prefix}/images/products_gallery_images/    ← gallery images (underscore — verified from F236/596)

prefix = S3_OPS_ENV_PREFIX (default "ctmediaon_staging" for staging,
         "ctmediaon" for production).
"""
import io
import logging
import os

import boto3
import httpx
from PIL import Image

logger = logging.getLogger(__name__)

_BUCKET = os.getenv("S3_PRODUCT_IMAGES_BUCKET", "ctmediaimg")
_ACCESS_KEY = os.getenv("S3_ACCESS_KEY_ID")
_SECRET_KEY = os.getenv("S3_SECRET_ACCESS_KEY")
_REGION = os.getenv("S3_REGION", "us-west-1")
_PREFIX = os.getenv("S3_OPS_ENV_PREFIX", "ctmediaon_staging")

_PRODUCT_FOLDER = f"{_PREFIX}/images/product/"
_GALLERY_FOLDER = f"{_PREFIX}/images/products_gallery_images/"


def _s3():
    return boto3.client(
        "s3",
        aws_access_key_id=_ACCESS_KEY,
        aws_secret_access_key=_SECRET_KEY,
        region_name=_REGION,
    )


_THUMB_SIZE = (300, 300)


async def _upload(url: str, folder: str) -> str:
    """Download image from URL and PUT to OPS S3. Returns bare filename."""
    filename = url.rsplit("/", 1)[-1].split("?")[0]
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    content_type = resp.headers.get("content-type", "image/jpeg")
    key = f"{folder}{filename}"
    _s3().put_object(Bucket=_BUCKET, Key=key, Body=resp.content, ContentType=content_type, ACL="public-read")
    logger.info("s3 upload: %s -> s3://%s/%s", url, _BUCKET, key)
    return filename, resp.content, content_type


async def upload_product_image(url: str) -> str:
    """Upload to product/ folder (used for imagename + product_desc_image)."""
    filename, _, _ = await _upload(url, _PRODUCT_FOLDER)
    return filename


async def upload_gallery_image(url: str) -> str:
    """Upload main + _thumb to gallery folder. Returns bare filename (without _thumb suffix)."""
    filename, raw_bytes, content_type = await _upload(url, _GALLERY_FOLDER)

    # Generate and upload thumbnail — OPS admin loads filename_thumb.ext automatically.
    try:
        base, ext = os.path.splitext(filename)
        thumb_filename = f"{base}_thumb{ext}"
        img = Image.open(io.BytesIO(raw_bytes))
        img.thumbnail(_THUMB_SIZE, Image.LANCZOS)
        buf = io.BytesIO()
        fmt = img.format or ("WEBP" if ext.lower() == ".webp" else "JPEG")
        img.save(buf, format=fmt)
        thumb_key = f"{_GALLERY_FOLDER}{thumb_filename}"
        _s3().put_object(Bucket=_BUCKET, Key=thumb_key, Body=buf.getvalue(), ContentType=content_type, ACL="public-read")
        logger.info("s3 thumb upload: s3://%s/%s", _BUCKET, thumb_key)
    except Exception as exc:
        logger.warning("thumb generation failed for %s: %s", filename, exc)

    return filename
