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

@router.post("/{customer_id}/{product_id}")
async def push_product_route(
    customer_id: UUID,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    from .service import push_product
    try:
        result = await push_product(db, customer_id, product_id)
        if result["status"] == "failed":
            raise HTTPException(500, result["message"])
        return result
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.get("/history/{customer_id}/{product_id}")
async def get_push_history(
    customer_id: UUID,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    from modules.push_log.models import ProductPushLog
    result = await db.execute(
        select(ProductPushLog)
        .where(
            ProductPushLog.customer_id == customer_id,
            ProductPushLog.product_id == product_id
        )
        .order_by(ProductPushLog.pushed_at.desc())
    )
    logs = result.scalars().all()
    return [
        {
            "id": log.id,
            "status": log.status,
            "error": log.error,
            "pushed_at": log.pushed_at,
            "ops_product_id": log.ops_product_id
        }
        for log in logs
    ]
