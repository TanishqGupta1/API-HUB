from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.ps_directory.client import get_ps_endpoints

from .models import Supplier


async def get_cached_endpoints(db: AsyncSession, supplier_id) -> list[dict]:
    """Return cached PS endpoints, refreshing if older than 24 hours."""
    result = await db.execute(select(Supplier).where(Supplier.id == supplier_id))
    supplier = result.scalar_one_or_none()
    if not supplier or not supplier.promostandards_code:
        return []

    # Check cache freshness
    if supplier.endpoint_cache and supplier.endpoint_cache_updated_at:
        age = datetime.now(timezone.utc) - supplier.endpoint_cache_updated_at
        if age < timedelta(hours=24):
            return supplier.endpoint_cache

    # Refresh from PS directory API
    import httpx
    import logging
    from fastapi import HTTPException
    _log = logging.getLogger(__name__)
    
    try:
        endpoints = await get_ps_endpoints(supplier.promostandards_code)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(
                404, 
                f"Supplier code '{supplier.promostandards_code}' not found in PromoStandards directory. "
                "Please verify the code is correct (usually lowercase)."
            )
        raise HTTPException(502, f"PromoStandards directory returned error: {e.response.status_code}")
    except httpx.ConnectError:
        raise HTTPException(504, "Connection to PromoStandards directory timed out. Check your internet/proxy settings.")
    except Exception as e:
        _log.error("Failed to fetch endpoints for %s: %s", supplier.promostandards_code, e)
        raise HTTPException(502, f"Failed to reach PromoStandards directory: {str(e)}")
    
    if not endpoints:
        raise HTTPException(502, f"PromoStandards directory returned no endpoints for '{supplier.promostandards_code}'.")

    supplier.endpoint_cache = endpoints
    supplier.endpoint_cache_updated_at = datetime.now(timezone.utc)
    await db.commit()
    return endpoints
