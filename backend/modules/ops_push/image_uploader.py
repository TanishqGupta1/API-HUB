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

def _s3():
    # Read credentials at call time (not import time) so load_dotenv() in
    # database.py has already run by the time the first upload happens.
    return boto3.client(
        "s3",
        aws_access_key_id=os.getenv("S3_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("S3_SECRET_ACCESS_KEY"),
        region_name=os.getenv("S3_REGION", "us-west-1"),
    )


def _bucket() -> str:
    return os.getenv("S3_PRODUCT_IMAGES_BUCKET", "ctmediaimg")


def _prefix() -> str:
    return os.getenv("S3_OPS_ENV_PREFIX", "ctmediaon_staging")


def _product_folder() -> str:
    return f"{_prefix()}/images/product/"


def _gallery_folder() -> str:
    return f"{_prefix()}/images/products_gallery_images/"


def _opt_gallery_folder() -> str:
    return f"{_prefix()}/images/opt/products_gallery_images/"


_THUMB_SIZE = (300, 300)


async def _upload(url: str, folder: str) -> str:
    """Download image from URL and PUT to OPS S3. Returns bare filename."""
    filename = url.rsplit("/", 1)[-1].split("?")[0]
    async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()
    bucket = _bucket()
    content_type = resp.headers.get("content-type", "image/jpeg")
    key = f"{folder}{filename}"
    _s3().put_object(Bucket=bucket, Key=key, Body=resp.content, ContentType=content_type, ACL="public-read")
    logger.info("s3 upload: %s -> s3://%s/%s", url, bucket, key)
    return filename, resp.content, content_type


async def upload_product_image(url: str) -> str:
    """Upload to product/ folder (used for imagename + product_desc_image)."""
    filename, _, _ = await _upload(url, _product_folder())
    return filename


async def upload_gallery_image(url: str) -> str:
    """Upload main + _thumb to gallery folder, and mirror to opt/ for storefront serving.

    OPS storefront serves gallery images from images/opt/products_gallery_images/ (CloudFront).
    Uploading directly to S3 bypasses OPS's image optimizer, so we mirror there manually.
    Returns bare filename (without _thumb suffix).
    """
    filename, raw_bytes, content_type = await _upload(url, _gallery_folder())
    s3 = _s3()
    bucket = _bucket()
    base, ext = os.path.splitext(filename)
    thumb_filename = f"{base}_thumb{ext}"

    # Generate thumbnail bytes once, reuse for both paths.
    thumb_bytes: bytes | None = None
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img.thumbnail(_THUMB_SIZE, Image.LANCZOS)
        buf = io.BytesIO()
        fmt = img.format or ("WEBP" if ext.lower() == ".webp" else "JPEG")
        img.save(buf, format=fmt)
        thumb_bytes = buf.getvalue()
        thumb_key = f"{_gallery_folder()}{thumb_filename}"
        s3.put_object(Bucket=bucket, Key=thumb_key, Body=thumb_bytes, ContentType=content_type, ACL="public-read")
        logger.info("s3 thumb upload: s3://%s/%s", bucket, thumb_key)
    except Exception as exc:
        logger.warning("thumb generation failed for %s: %s", filename, exc)

    opt = _opt_gallery_folder()
    # Mirror to opt/ folder — storefront CloudFront URLs point here.
    try:
        s3.put_object(Bucket=bucket, Key=f"{opt}{filename}", Body=raw_bytes, ContentType=content_type, ACL="public-read")
        if thumb_bytes:
            s3.put_object(Bucket=bucket, Key=f"{opt}{thumb_filename}", Body=thumb_bytes, ContentType=content_type, ACL="public-read")
        # WebP version — OPS srcset requests filename.ext.webp
        try:
            img2 = Image.open(io.BytesIO(raw_bytes))
            webp_buf = io.BytesIO()
            img2.save(webp_buf, format="WEBP", quality=85)
            s3.put_object(Bucket=bucket, Key=f"{opt}{filename}.webp", Body=webp_buf.getvalue(), ContentType="image/webp", ACL="public-read")
        except Exception as exc:
            logger.warning("webp generation failed for %s: %s", filename, exc)
        logger.info("s3 opt/ mirror: s3://%s/%s%s", bucket, opt, filename)
    except Exception as exc:
        logger.warning("opt/ mirror failed for %s: %s", filename, exc)

    return filename
