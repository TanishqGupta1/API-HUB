"""PromoStandards XML to ProductIngest normalizer (V2).

Pure XML parsing using lxml. Replaces the legacy DB-writing normalizer.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional, Any
from datetime import datetime

from lxml import etree
from pydantic import BaseModel

from modules.catalog.schemas import (
    ApparelDetailsIngest,
    ImageIngest,
    ProductIngest,
    VariantIngest,
    VariantPriceIngest,
)

# Shared price tier for internal merging
class PriceTier(BaseModel):
    group_name: str
    qty_min: int
    qty_max: int
    price: Decimal
    currency: str = "USD"
    effective_from: Optional[datetime] = None

def _text(node: Any, xpath: str) -> Optional[str]:
    res = node.xpath(xpath)
    return res[0].text if res and res[0].text else None

def _parse_iso(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except ValueError:
        return None

_MEDIA_CLASS_TO_TYPE = {
    "primary": "front",
    "front model": "front",
    "frontModel": "front",
    "back model": "back",
    "backModel": "back",
    "rear model": "back",
    "swatch": "swatch",
}

def normalize_get_product_xml(xml_bytes: bytes) -> ProductIngest:
    """Parse GetProductResponse XML into a base ProductIngest (without media/pricing)."""
    root = etree.fromstring(xml_bytes)
    # local-name() is used to be namespace-agnostic across different PS implementations
    product = root.xpath("//*[local-name()='Product']")[0]
    
    product_id = _text(product, "*[local-name()='productId']")
    name = _text(product, "*[local-name()='productName']")
    brand = _text(product, "*[local-name()='productBrand']")
    
    # Description can be multiple nodes in SanMar
    desc_nodes = product.xpath("*[local-name()='description']")
    description = "\n".join(d.text for d in desc_nodes if d.text)

    cat_node = product.xpath("*[local-name()='ProductCategoryArray']/*[local-name()='ProductCategory']")
    cat_name = _text(cat_node[0], "*[local-name()='category']") if cat_node else None
    cat_external_id = cat_name # Use name as ID if not specified

    last_change = _parse_iso(_text(product, "*[local-name()='lastChangeDate']"))
    is_closeout = _text(product, "*[local-name()='isCloseout']") == "true"
    is_caution = _text(product, "*[local-name()='isCaution']") == "true"
    caution_comment = _text(product, "*[local-name()='cautionComment']")

    variants: list[VariantIngest] = []
    part_nodes = product.xpath("*[local-name()='ProductPartArray']/*[local-name()='ProductPart']")
    
    for part in part_nodes:
        part_id = _text(part, "*[local-name()='partId']")
        color_node = part.xpath("*[local-name()='primaryColor']/*[local-name()='Color']") or part.xpath("*[local-name()='ColorArray']/*[local-name()='Color']")
        color_name = _text(color_node[0], "*[local-name()='colorName']") if color_node else None
        std_color = _text(color_node[0], "*[local-name()='standardColorName']") if color_node else None
        
        size_node = part.xpath("*[local-name()='ApparelSize']")
        label_size = _text(size_node[0], "*[local-name()='labelSize']") if size_node else None
        
        gtin = _text(part, "*[local-name()='gtin']")

        variants.append(VariantIngest(
            part_id=part_id,
            color=std_color or color_name,
            size=label_size,
            sku=part_id,
            gtin=gtin,
            prices=[],
        ))

    # Parse MSRP if present in ProductData (common in PS 2.0.0)
    msrp_tiers: list[VariantPriceIngest] = []
    group_nodes = product.xpath("*[local-name()='ProductPriceGroupArray']/*[local-name()='ProductPriceGroup']")
    for group in group_nodes:
        group_name = _text(group, "*[local-name()='groupName']") or "MSRP"
        for price in group.xpath("*[local-name()='ProductPriceArray']/*[local-name()='ProductPrice']"):
            qmin = _text(price, "*[local-name()='quantityMin']")
            value = _text(price, "*[local-name()='price']")
            if value:
                msrp_tiers.append(VariantPriceIngest(
                    price_type=group_name,
                    quantity_min=int(qmin) if qmin else 1,
                    price=Decimal(value),
                ))
    
    if msrp_tiers:
        for v in variants:
            v.prices.extend(msrp_tiers)

    primary_image = _text(product, "*[local-name()='primaryImageUrl']") or _text(product, "*[local-name()='primaryImageURL']")

    apparel_details = ApparelDetailsIngest(
        pricing_method="tiered_variants"
    )

    return ProductIngest(
        supplier_sku=product_id,
        product_name=name or product_id,
        brand=brand,
        description=description,
        product_type="apparel",
        image_url=primary_image,
        category_name=cat_name,
        category_external_id=cat_external_id,
        variants=variants,
        images=[ImageIngest(url=primary_image, image_type="primary")] if primary_image else [],
        apparel_details=apparel_details,
        raw_payload={"normalized_from": "PromoStandards V2"}
    )

def merge_pricing(ingest: ProductIngest, pricing_xml: bytes) -> ProductIngest:
    """Append PartPriceArray tiers (Net, Sale, Case, ...) onto each variant."""
    root = etree.fromstring(pricing_xml)
    parts = root.xpath("//*[local-name()='PartPricing'] | //*[local-name()='Part']")
    by_part = {v.part_id: v for v in ingest.variants}
    
    for part in parts:
        pid = _text(part, "*[local-name()='partId']")
        if not pid or pid not in by_part:
            continue
            
        price_nodes = part.xpath("*[local-name()='PriceArray']/*[local-name()='Price'] | *[local-name()='PartPriceArray']/*[local-name()='PartPrice']")
        for pp in price_nodes:
            qmin = _text(pp, "*[local-name()='minQuantity'] | *[local-name()='quantityMin']")
            value = _text(pp, "*[local-name()='price']")
            discount_code = _text(pp, "*[local-name()='discountCode']") or "Net"
            if not value:
                continue
            
            by_part[pid].prices.append(VariantPriceIngest(
                price_type=discount_code,
                quantity_min=int(qmin) if qmin else 1,
                price=Decimal(value),
            ))
    return ingest

def merge_media(ingest: ProductIngest, media_xml: bytes) -> ProductIngest:
    """Append MediaContentArray entries to ingest.images."""
    root = etree.fromstring(media_xml)
    seen_urls = {img.url for img in ingest.images}
    media_nodes = root.xpath("//*[local-name()='MediaContent']")
    
    for media in media_nodes:
        url = _text(media, "*[local-name()='url']")
        if not url or url in seen_urls:
            continue
            
        class_name = _text(media, "*[local-name()='classTypeName']")
        kind = _MEDIA_CLASS_TO_TYPE.get((class_name or "").lower(), "front")
        color = _text(media, "*[local-name()='colorName']") or _text(media, "*[local-name()='color']")
        
        ingest.images.append(ImageIngest(
            url=url,
            image_type=kind,
            color=color,
        ))
        seen_urls.add(url)
    return ingest
