"""Alphabroder PromoStandards SOAP adapter.

Alphabroder implements the full PromoStandards SOAP spec.
This is a thin subclass of PromoStandardsAdapter that provides
hardcoded WSDL fallbacks if the supplier's endpoint_cache is not yet
populated from the PS Directory.

Credentials in auth_config: {"id": "...", "password": "..."}
"""
from __future__ import annotations

from modules.import_jobs.registry import register_adapter
from .adapter import PromoStandardsAdapter

ALPHABRODER_WSDLS = {
    "PRODUCT": "https://services.alphabroder.com/productData2/wsdl/ProductDataService.wsdl",
    "MEDIA": "https://services.alphabroder.com/ppc/wsdl/MediaContentService.wsdl",
    "PRICING": "https://services.alphabroder.com/ppc/wsdl/PricingAndConfigurationService.wsdl",
    "INVENTORY": "https://services.alphabroder.com/ppc/wsdl/InventoryService.wsdl",
}


class AlphabroderAdapter(PromoStandardsAdapter):
    """Alphabroder SOAP adapter — subclass with hardcoded WSDL fallbacks."""

    def _wsdl_for(self, service_type: str) -> str:
        # PS Directory endpoint_cache takes priority (populated by /api/ps/resolve)
        try:
            cached = super()._wsdl_for(service_type)
            if cached:
                return cached
        except Exception:
            pass

        url = ALPHABRODER_WSDLS.get(service_type.upper())
        if url:
            return url

        return super()._wsdl_for(service_type)


register_adapter("AlphabroderAdapter", AlphabroderAdapter)
