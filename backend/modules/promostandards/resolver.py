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
        # Try both ServiceType and Name fields — suppliers use different keys
        raw_type = ep.get("ServiceType") or ep.get("Name") or ""
        if _normalize_service_type(raw_type) == target:
            url = ep.get("ProductionURL")
            if url:
                return url
    return None
