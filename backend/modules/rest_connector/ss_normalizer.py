"""S&S Activewear JSON normalizer."""

import logging
from collections import defaultdict
from modules.promostandards.schemas import (
    PSProductData,
    PSProductPart,
    PSInventoryLevel,
    PSPricePoint,
    PSMediaItem,
)

logger = logging.getLogger(__name__)

def ss_to_ps_format(
    ss_products: list[dict],
) -> tuple[
    list[PSProductData],
    list[PSInventoryLevel],
    list[PSPricePoint],
    list[PSMediaItem],
]:
    """Group S&S part rows by styleID -> emit PS-format typed models."""
    
    products_by_style: dict[str, dict] = {}
    parts_by_style: dict[str, list[PSProductPart]] = defaultdict(list)
    media_by_style: dict[str, dict[str, PSMediaItem]] = defaultdict(dict)
    
    inventories: list[PSInventoryLevel] = []
    prices: list[PSPricePoint] = []
    
    for row in ss_products:
        # Validate critical identifiers
        style_id = row.get("styleID")
        sku = row.get("sku")
        
        if not style_id or not sku:
            logger.warning(f"Skipping malformed S&S row: styleID={style_id}, sku={sku}")
            continue

        style_id_str = str(style_id)
        sku_str = str(sku)
        
        # 1. Product extraction mapping
        if style_id_str not in products_by_style:
            products_by_style[style_id_str] = {
                "product_id": style_id_str,
                "product_name": row.get("styleName", "Unknown Product"),
                "brand": row.get("brandName"),
                "description": row.get("styleDescription", ""),
                "categories": [row.get("categoryName")] if row.get("categoryName") else [],
                "product_type": "apparel",
            }
            
        # 2. Product Part mapping
        part = PSProductPart(
            part_id=sku_str,
            color_name=row.get("colorName"),
            size_name=row.get("sizeName"),
            description=None
        )
        parts_by_style[style_id_str].append(part)
        
        # 3. Inventory Mapping
        inventories.append(
            PSInventoryLevel(
                product_id=style_id_str,
                part_id=sku_str,
                quantity_available=min(int(row.get("qty", 0)), 500) if row.get("qty") is not None else 0,
                warehouse_code=row.get("warehouseAbbr")
            )
        )
        
        # 4. Pricing Mapping
        if "yourPrice" in row and row["yourPrice"] is not None:
            prices.append(
                PSPricePoint(
                    product_id=style_id_str,
                    part_id=sku_str,
                    price=float(row["yourPrice"]),
                    quantity_min=1,
                    price_type="piece"
                )
            )
            
        # 5. Media Item mapping (deduped by color/url)
        img_url = row.get("colorFrontImage")
        color = row.get("colorName")
        if img_url:
            media_key = f"{color}_{img_url}"
            if media_key not in media_by_style[style_id_str]:
                media_by_style[style_id_str][media_key] = PSMediaItem(
                    product_id=style_id_str,
                    url=img_url,
                    media_type="front",
                    color_name=color
                )

    # Compile the final lists
    products: list[PSProductData] = []
    all_media: list[PSMediaItem] = []
    
    for style_id_str, prod_dict in products_by_style.items():
        prod_dict["parts"] = parts_by_style[style_id_str]
        products.append(PSProductData(**prod_dict))
        all_media.extend(media_by_style[style_id_str].values())
        
    return products, inventories, prices, all_media
