"""OPS push endpoints — image processing, payload preview, and push execution."""

from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.catalog.models import ProductImage
from modules.decorations.service import DecorationMissingError

from .image_pipeline import process_image
from .service import execute_push, prepare_push_payload

router = APIRouter(prefix="/api/push", tags=["ops_push"])
push_action_router = APIRouter(prefix="/api/customers", tags=["ops_push"])


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


@router.get("/payload/{customer_id}/{product_id}")
async def preview_push_payload(
    customer_id: UUID,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Preview the push payload that would be sent to n8n (no side-effects)."""
    try:
        payload = await prepare_push_payload(customer_id, product_id, db)
    except DecorationMissingError as e:
        raise HTTPException(422, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))
    # Strip secret from preview
    payload.pop("customer_ops_client_secret", None)
    return payload


@push_action_router.post("/{customer_id}/push/{product_id}", status_code=202)
async def push_product(
    customer_id: UUID,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Validate, log, and trigger n8n push for a product to a customer storefront."""
    try:
        log, payload = await execute_push(customer_id, product_id, db)
    except DecorationMissingError as e:
        raise HTTPException(422, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))

    # Strip secret before returning to caller
    payload.pop("customer_ops_client_secret", None)
    return {
        "push_log_id": str(log.id),
        "status": log.status,
        "payload": payload,
    }
