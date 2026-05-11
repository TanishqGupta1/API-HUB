from typing import Any

def merge_product_with_decorations(product: Any, customer_id: Any, decorations: list[dict] | None) -> dict:
    """
    Merges base product data with decoration overlays for the OPS push payload.
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
                "method": dec.get("method"),
                "price": float(dec.get("price_addition", 0.0) or 0.0)
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
            
    # Decide which image to push
    # If we have decorations, we push the "Branded Mockup" from our engine
    import os
    api_url = os.getenv("API_BASE_URL", "http://localhost:8000").rstrip("/")
    
    if decorations:
        image_url = f"{api_url}/api/customers/{customer_id}/products/{product.id}/decorations/preview.png"
    else:
        image_url = product.image_url

    payload = {
        "external_id": product.supplier_sku,
        "name": product.product_name,
        "description": product.description,
        "brand": product.brand,
        "categories": [product.category] if product.category else [],
        "type": product.product_type,
        "image_url": image_url,
        "variants": variants
    }
    
    return payload
