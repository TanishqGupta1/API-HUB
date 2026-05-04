from typing import Any

def merge_product_with_decorations(product: Any, decorations: list[dict] | None) -> dict:
    """
    Merges base product data with decoration overlays for the OPS push payload.
    
    Rules:
    - Preserve base variants (color, size, SKU)
    - Add decoration areas (front, back, sleeve) and print methods (DTG, embroidery, etc)
    - Pricing: base price + decoration cost
    """
    
    # Extract base variants
    variants = []
    
    # Common decoration processing
    dec_cost = 0.0
    dec_areas = []
    if decorations:
        for dec in decorations:
            dec_cost += float(dec.get("price_addition", 0.0) or 0.0)
            dec_areas.append({
                "placement": dec.get("placement"),
                "method": dec.get("method")
            })

    if hasattr(product, "variants") and product.variants:
        for v in product.variants:
            base_price = float(v.base_price) if v.base_price else 0.0
            final_price = base_price + dec_cost
            
            variants.append({
                "sku": v.sku,
                "color": v.color,
                "size": v.size,
                "inventory": v.inventory,
                "price": final_price,
                "decorations": dec_areas
            })
    elif decorations:
        # Fallback for products without variants but with decorations
        variants.append({
            "sku": product.supplier_sku,
            "color": "Default",
            "size": "OS",
            "inventory": 0,
            "price": dec_cost,
            "decorations": dec_areas
        })
            
    payload = {
        "external_id": product.supplier_sku,
        "name": product.product_name,
        "description": product.description,
        "brand": product.brand,
        "categories": [product.category] if product.category else [],
        "type": product.product_type,
        "variants": variants
    }
    
    return payload
