"""OPS push endpoints — image processing and product payloads."""

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.models import ProductImage

from .image_pipeline import process_image

router = APIRouter(prefix="/api/push", tags=["ops_push"])


@router.get("/image/{image_id}/processed")
async def get_processed_image(
    image_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Fetch a ProductImage row, download its URL, process it, return WebP bytes.

    n8n calls this when pushing a product to OPS — the WebP bytes are then
    uploaded via setOrderProductImage.
    """
    result = await db.execute(select(ProductImage).where(ProductImage.id == image_id))
    image = result.scalar_one_or_none()
    if not image:
        raise HTTPException(404, "Image not found")

    try:
        webp_bytes = await process_image(image.url)
    except httpx.HTTPError as e:
        raise HTTPException(502, f"Failed to download source image: {e}")
    except Exception as e:
        raise HTTPException(500, f"Failed to process image: {e}")

    return Response(
        content=webp_bytes,
        media_type="image/webp",
        headers={"Cache-Control": "public, max-age=86400"},
    )
