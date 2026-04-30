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


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string like '2.0.0' into a tuple for comparison."""
    try:
        return tuple(int(x) for x in str(version_str).split("."))
    except (ValueError, AttributeError):
        return (0,)


def resolve_wsdl_url(endpoint_cache: list[dict], service_type: str) -> str | None:
    """Find the ProductionURL for a given service type in the cached endpoints.

    When multiple versions of the same service exist, returns the highest version.

    Args:
        endpoint_cache: List of endpoint dicts from PS directory API.
            Each dict has keys like ServiceType, ProductionURL, TestURL, Version, Name.
        service_type: One of "product_data", "inventory", "ppc", "media".

    Returns:
        The ProductionURL string, or None if not found.
    """
    target = _normalize_service_type(service_type)
    best_url: str | None = None
    best_version: tuple[int, ...] = (-1,)

    for ep in endpoint_cache or []:
        raw_type = ""
        version_str = "0"
        service_block = ep.get("Service")
        if isinstance(service_block, dict):
            st = service_block.get("ServiceType")
            if isinstance(st, dict):
                raw_type = st.get("Name", "")
            else:
                raw_type = str(st or "")
            version_str = service_block.get("Version", "0")

        if not raw_type:
            raw_type = ep.get("ServiceType") or ep.get("Name") or ""
        if not version_str or version_str == "0":
            version_str = ep.get("Version", "0")

        if _normalize_service_type(str(raw_type)) != target:
            continue

        url = ep.get("URL") or ep.get("ProductionURL")
        if not url:
            continue

        version = _parse_version(version_str)
        if version > best_version:
            best_version = version
            best_url = url

    return best_url
