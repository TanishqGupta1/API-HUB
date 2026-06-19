"""S3/R2 storage backend for product images.

Configurable via env vars — works with AWS S3 or Cloudflare R2 (S3-compatible):
  S3_ACCESS_KEY_ID       — access key
  S3_SECRET_ACCESS_KEY   — secret key
  S3_REGION              — region (default: auto, for R2 use "auto")
  S3_ENDPOINT_URL        — custom endpoint (R2: https://<account>.r2.cloudflarestorage.com)
  S3_PRODUCT_IMAGES_BUCKET — bucket name (default: product-images-dev)
  S3_OBJECT_ACL          — per-object ACL, e.g. "public-read" for buckets that
                           gate public access per-object (unset = bucket default;
                           R2 does not support ACLs, leave unset there)
  CDN_BASE_URL           — public CDN prefix returned in URLs
"""

import asyncio
import logging
import os
from functools import lru_cache
from typing import Optional

log = logging.getLogger(__name__)

S3_BUCKET = os.getenv("S3_PRODUCT_IMAGES_BUCKET", "product-images-dev")
# CDN_BASE_URL must be explicitly set — no default so that is_own_cdn() never
# accidentally matches in dev/test environments (avoids treating every mock-upload
# as "already mirrored" when CDN_BASE_URL is unset).
CDN_BASE_URL = os.getenv("CDN_BASE_URL", "").rstrip("/")

_IS_CONFIGURED = bool(
    os.getenv("S3_ACCESS_KEY_ID") and os.getenv("S3_SECRET_ACCESS_KEY")
)


@lru_cache(maxsize=1)
def _build_client():
    import boto3  # imported lazily so the module loads fine without boto3 installed

    kwargs: dict = {
        "aws_access_key_id": os.getenv("S3_ACCESS_KEY_ID"),
        "aws_secret_access_key": os.getenv("S3_SECRET_ACCESS_KEY"),
        "region_name": os.getenv("S3_REGION", "auto"),
    }
    endpoint = os.getenv("S3_ENDPOINT_URL")
    if endpoint:
        kwargs["endpoint_url"] = endpoint
    return boto3.client("s3", **kwargs)


def _is_configured() -> bool:
    return bool(os.getenv("S3_ACCESS_KEY_ID") and os.getenv("S3_SECRET_ACCESS_KEY"))


async def upload_image(data: bytes, key: str, content_type: str = "image/webp") -> str:
    """Upload bytes to S3/R2. Returns the public CDN URL.

    When S3 credentials are not configured (local dev), logs a warning and returns
    a predictable mock URL so the rest of the pipeline still runs.
    """
    if not _is_configured():
        log.warning("S3 credentials not configured — skipping real upload for key=%s", key)
        return f"{CDN_BASE_URL}/{key}"

    client = _build_client()
    bucket = S3_BUCKET

    def _put():
        kwargs: dict = {
            "Bucket": bucket,
            "Key": key,
            "Body": data,
            "ContentType": content_type,
            "CacheControl": "public, max-age=31536000, immutable",
        }
        acl = os.getenv("S3_OBJECT_ACL")
        if acl:
            kwargs["ACL"] = acl
        client.put_object(**kwargs)

    await asyncio.to_thread(_put)
    log.debug("Uploaded %d bytes to s3://%s/%s", len(data), bucket, key)
    return f"{CDN_BASE_URL}/{key}"


async def get_object_bytes(key: str) -> Optional[bytes]:
    """Fetch an object's bytes from S3/R2. Returns None when unconfigured or missing."""
    if not _is_configured():
        return None

    client = _build_client()
    bucket = S3_BUCKET

    def _get() -> Optional[bytes]:
        try:
            return client.get_object(Bucket=bucket, Key=key)["Body"].read()
        except Exception:
            return None

    return await asyncio.to_thread(_get)


async def key_exists(key: str) -> bool:
    """Return True if the S3 key already exists (head_object check)."""
    if not _is_configured():
        return False

    client = _build_client()
    bucket = S3_BUCKET

    def _head() -> bool:
        try:
            client.head_object(Bucket=bucket, Key=key)
            return True
        except Exception:
            return False

    return await asyncio.to_thread(_head)


async def get_object_size(key: str) -> Optional[int]:
    """Return the byte size of an S3 object, or None if missing/unconfigured.

    Used to filter out tiny supplier images (color-swatch chips ~60-100b)
    that aren't real product photos and would clutter the OPS gallery.
    """
    if not _is_configured():
        return None

    client = _build_client()
    bucket = S3_BUCKET

    def _head() -> Optional[int]:
        try:
            return client.head_object(Bucket=bucket, Key=key)["ContentLength"]
        except Exception:
            return None

    return await asyncio.to_thread(_head)


def cdn_url(key: str) -> str:
    return f"{CDN_BASE_URL}/{key}"


def is_own_cdn(url: Optional[str]) -> bool:
    """Return True if a URL is already hosted on our CDN (already mirrored).

    Returns False when CDN_BASE_URL is unset (empty string sentinel) so that
    dev environments with no S3 configured never treat any URL as mirrored.
    """
    if not CDN_BASE_URL:
        return False
    return bool(url and url.startswith(CDN_BASE_URL + "/"))
