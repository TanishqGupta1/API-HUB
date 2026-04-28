"""Pydantic models for deserialized PromoStandards SOAP responses.

These are NOT database models. They are typed containers for parsed XML,
giving the normalizer clean input regardless of which supplier the data came from.
"""

from pydantic import BaseModel


class PSProductPart(BaseModel):
    """A single color/size variant from getProduct response.

    SanMar calls these 'parts' — one 'PC61 Essential Tee' product has
    parts like 'Navy/M', 'Navy/L', 'White/S'.

    The optional ``attributes`` dict is used by the 4Over normalizer to carry
    print-specific axes (coating, paper_weight, fold, etc.) that don't fit
    naturally into ``color_name`` / ``size_name``. SanMar's SOAP normalizer
    never sets it, so defaulting to an empty dict is backward-compatible.
    """
    part_id: str
    color_name: str | None = None
    size_name: str | None = None
    description: str | None = None
    attributes: dict[str, str] = {}


class PSProductData(BaseModel):
    """A product from getProduct or getProductSellable response."""
    product_id: str
    product_name: str | None = None
    description: str | None = None
    brand: str | None = None
    categories: list[str] = []
    product_type: str = "apparel"
    primary_image_url: str | None = None
    parts: list[PSProductPart] = []


class PSInventoryLevel(BaseModel):
    """Inventory for one part from getInventoryLevels response.

    quantity_available is capped at 500 per PromoStandards convention.
    """
    product_id: str
    part_id: str
    quantity_available: int = 0
    warehouse_code: str | None = None


class PSPricePoint(BaseModel):
    """Price for one part from PPC (Pricing & Configuration) service."""
    product_id: str
    part_id: str
    price: float
    quantity_min: int = 1
    quantity_max: int | None = None
    price_type: str = "piece"  # piece, dozen, case


class PSMediaItem(BaseModel):
    """An image/media asset from Media Content service."""
    product_id: str
    url: str
    media_type: str = "front"  # front, back, side, swatch, detail
    color_name: str | None = None


class PSCategoryData(BaseModel):
    """A browseable supplier catalog category.

    Not from PromoStandards spec — SanMar ships a fixed ~40-category list in
    their Web Services Integration Guide (see sanmar/SanMar-Web-Services-
    Integration-Guide-24.3.pdf p25-33). Other suppliers may provide categories
    via their own endpoints; this schema is the common return shape.
    """
    name: str
    slug: str | None = None
    product_count: int | None = None
    preview_image_url: str | None = None
