"""Image processing pipeline for OPS push.

Downloads an image URL from a supplier CDN, resizes it to 800x800 max,
converts to WebP quality 85, and returns the processed bytes.
"""

from io import BytesIO

import httpx
from PIL import Image


async def process_image(source_url: str) -> bytes:
    """Download, resize to 800x800, convert to WebP q85.

    Args:
        source_url: Full URL of the source image (e.g. supplier CDN).

    Returns:
        Processed image as WebP bytes.

    Raises:
        httpx.HTTPError: if the download fails.
        PIL.UnidentifiedImageError: if the response is not a valid image.
    """
    # Download
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        r = await client.get(source_url)
        r.raise_for_status()

    # Open, convert to RGB (WebP does not support all modes), resize in-place
    img = Image.open(BytesIO(r.content)).convert("RGB")
    img.thumbnail((800, 800), Image.Resampling.LANCZOS)

    # Encode as WebP quality 85
    out = BytesIO()
    img.save(out, format="WEBP", quality=85)
    return out.getvalue()
