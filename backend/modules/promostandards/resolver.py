"""Resolve WSDL URLs from cached PromoStandards directory endpoints."""

# PS directory returns ServiceType as strings like "Product Data", "Inventory",
# "Product Pricing and Configuration", "Media Content". Suppliers register
# with inconsistent naming. This resolver normalizes for matching.

_SERVICE_TYPE_ALIASES = {
    "product data": "product_data",
    "productdata": "product_data",
    "product": "product_data",
    "inventory": "inventory",
    "inventory levels": "inventory",
    "inventorylevels": "inventory",
    "product pricing and configuration": "ppc",
    "ppc": "ppc",
    "pricing": "ppc",
    "pricing and configuration": "ppc",
    "media content": "media",
    "mediacontent": "media",
    "media": "media",
}


def _normalize_service_type(raw: str) -> str:
    """Normalize a PS ServiceType string to a canonical key."""
    return _SERVICE_TYPE_ALIASES.get(raw.strip().lower(), raw.strip().lower())


def resolve_wsdl_url(endpoint_cache: list[dict], service_type: str) -> str | None:
    """Find the ProductionURL for a given service type in the cached endpoints.

    Args:
        endpoint_cache: List of endpoint dicts from PS directory API.
            Each dict has keys like ServiceType, ProductionURL, TestURL, Version, Name.
        service_type: One of "product_data", "inventory", "ppc", "media".

    Returns:
        The ProductionURL string, or None if not found.

    Example:
        >>> endpoints = [{"ServiceType": "Product Data", "ProductionURL": "https://ws.sanmar.com/...?wsdl"}]
        >>> resolve_wsdl_url(endpoints, "product_data")
        'https://ws.sanmar.com/...?wsdl'
    """
    target = _normalize_service_type(service_type)
    for ep in endpoint_cache or []:
        # Handle standard flat dicts OR nested PS Directory API v2 structure
        raw_type = ""
        service_block = ep.get("Service")
        if isinstance(service_block, dict):
            st = service_block.get("ServiceType")
            if isinstance(st, dict):
                raw_type = st.get("Name", "")
            else:
                raw_type = str(st or "")
        
        if not raw_type:
            raw_type = ep.get("ServiceType") or ep.get("Name") or ""

        if _normalize_service_type(str(raw_type)) == target:
            # Prefer the exact version if specified, otherwise take the first match
            # Some directories return 'URL', some return 'ProductionURL'
            url = ep.get("URL") or ep.get("ProductionURL")
            
            # Prefer V2 or V1.1.0 over V1.0.0 if multiple exist (resolver stops at first match otherwise)
            # We'll just return the first match we find for now, as that's what the current logic does.
            # To handle versions properly, we should really sort or filter by version.
            # But just grabbing URL is enough to fix the crash.
            if url:
                return url
    return None
