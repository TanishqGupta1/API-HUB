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
    if hasattr(product, "variants") and product.variants:
        for v in product.variants:
            base_price = float(v.base_price) if v.base_price else 0.0
            
            # If decorations exist, we could add decoration cost.
            # Assuming decoration_options adds a fixed cost for simplicity here, 
            # or we calculate based on the complex decoration pricing model.
            dec_cost = 0.0
            dec_areas = []
            
            if decorations:
                for dec in decorations:
                    # dec might look like {"placement": "Front", "method": "DTG", "price_addition": 5.0}
                    # We extract cost if it exists
                    dec_cost += float(dec.get("price_addition", 0.0) or 0.0)
                    dec_areas.append({
                        "placement": dec.get("placement"),
                        "method": dec.get("method")
                    })
            
            final_price = base_price + dec_cost
            
            variants.append({
                "sku": v.sku,
                "color": v.color,
                "size": v.size,
                "inventory": v.inventory,
                "price": final_price,
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
