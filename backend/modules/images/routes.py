"""Image mirroring admin endpoints.

POST /api/images/mirror/{product_id}   — mirror one product immediately (sync)
POST /api/images/mirror-batch          — mirror many products in background (202)
GET  /api/images/mirror-status/{product_id} — mirror status for a product
"""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.auth.dependencies import VGAdmin
from modules.catalog.models import ProductImage
from modules.catalog.schemas import ProductImageOpsFilenameUpdate, ProductImageRead
from modules.images.mirror import mirror_product_images, mirror_products_batch
from modules.images.storage import is_own_cdn

router = APIRouter(prefix="/api/images", tags=["images"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class MirrorResult(BaseModel):
    product_id: str
    mirrored: int
    skipped: int
    failed: int
    error: Optional[str] = None


class BatchMirrorRequest(BaseModel):
    product_ids: list[UUID] = Field(..., min_length=1, max_length=200)


class BatchMirrorAccepted(BaseModel):
    accepted: int
    message: str


class ImageMirrorStatus(BaseModel):
    product_id: str
    total_images: int
    mirrored_images: int
    pending_images: int
    last_fetch_at: Optional[str]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/mirror/{product_id}", response_model=MirrorResult)
async def mirror_product(
    product_id: UUID,
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
) -> MirrorResult:
    """Mirror all images for a single product. Runs synchronously (waits for completion)."""
    result = await mirror_product_images(product_id, db)
    if result.get("error"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, result["error"])
    return MirrorResult(**result)


@router.post("/mirror-batch", response_model=BatchMirrorAccepted, status_code=202)
async def mirror_batch(
    body: BatchMirrorRequest,
    background_tasks: BackgroundTasks,
    _: VGAdmin,
) -> BatchMirrorAccepted:
    """Queue mirroring for up to 200 products. Returns 202 immediately."""
    background_tasks.add_task(mirror_products_batch, body.product_ids)
    return BatchMirrorAccepted(
        accepted=len(body.product_ids),
        message=f"Mirroring {len(body.product_ids)} product(s) in background",
    )


@router.patch("/{image_id}/ops-filename", response_model=ProductImageRead)
async def set_ops_filename(
    image_id: UUID,
    body: ProductImageOpsFilenameUpdate,
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
) -> ProductImageRead:
    """Set (or clear) the OPS media filename on a product image row.

    Call this after manually uploading the image via the OPS admin UI.
    The push gateway reads ops_filename as products_large_image_name in
    setProductsImageGallery — images without this field are skipped.
    Pass ops_filename=null to clear a previously set value.
    """
    img = await db.get(ProductImage, image_id)
    if img is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Image {image_id} not found")
    img.ops_filename = body.ops_filename
    await db.commit()
    await db.refresh(img)
    return ProductImageRead.model_validate(img)


@router.get("/mirror-status/{product_id}", response_model=ImageMirrorStatus)
async def mirror_status(
    product_id: UUID,
    _: VGAdmin,
    db: AsyncSession = Depends(get_db),
) -> ImageMirrorStatus:
    """Return mirror status (how many images are on our CDN vs still on supplier CDN)."""
    from modules.catalog.models import Product, ProductImage

    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")

    images_q = await db.execute(
        select(ProductImage).where(ProductImage.product_id == product_id)
    )
    images = list(images_q.scalars().all())

    # An image is considered mirrored if mirrored_at is set OR url is on our CDN
    mirrored = sum(1 for img in images if img.mirrored_at or is_own_cdn(img.url))

    return ImageMirrorStatus(
        product_id=str(product_id),
        total_images=len(images),
        mirrored_images=mirrored,
        pending_images=len(images) - mirrored,
        last_fetch_at=product.last_image_fetch_at.isoformat() if product.last_image_fetch_at else None,
    )
