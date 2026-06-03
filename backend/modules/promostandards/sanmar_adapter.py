"""SanMar-specific PromoStandards adapter.

Overrides WSDL resolution and authentication payload to match SanMar's 
implementation of PromoStandards.
"""
from __future__ import annotations

import logging
from typing import Any

from modules.import_jobs.registry import register_adapter
from .adapter import PromoStandardsAdapter

log = logging.getLogger(__name__)

# PromoStandards production WSDL endpoints, per the SanMar Web Services
# Integration Guide v24.3 (sanmar/SanMar-Web-Services-Integration-Guide-24.3.pdf).
# The previous host `promostandards.sanmar.com` does not resolve — all SanMar
# web services (legacy + PromoStandards) are served from ws.sanmar.com:8080.
# Test host is test-ws.sanmar.com:8080 with the same paths.
SANMAR_WSDLS = {
    # Product Data Service v2.0.0 (guide p8)
    "PRODUCT": "https://ws.sanmar.com:8080/promostandards/ProductDataServiceBindingV2?WSDL",
    # Media Content Service v1.0.0 (guide p54)
    "MEDIA": "https://ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl",
    # Pricing and Configuration Service v1.0.0 (guide p81)
    "PRICING": "https://ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL",
    # Inventory Service v2.0.0 (guide p67)
    "INVENTORY": "https://ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL",
}


class SanMarAdapter(PromoStandardsAdapter):
    """Subclass for SanMar that uses hardcoded WSDLs and special auth."""

    def _wsdl_for(self, service_type: str) -> str:
        # 1. Try dynamic cache (PS Directory) first
        try:
            cached = super()._wsdl_for(service_type)
            if cached:
                return cached
        except Exception:
            pass
            
        # 2. Fallback to hardcoded SanMar defaults
        url = SANMAR_WSDLS.get(service_type.upper())
        if url:
            return url
            
        return super()._wsdl_for(service_type) # Let it raise the error if still missing


# Self-register
register_adapter("SanMarAdapter", SanMarAdapter)
