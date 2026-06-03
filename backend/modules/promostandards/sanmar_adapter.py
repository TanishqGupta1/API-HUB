"""SanMar-specific PromoStandards adapter.

Overrides WSDL resolution and authentication payload to match SanMar's
implementation of PromoStandards.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from modules.import_jobs.registry import register_adapter
from .adapter import PromoStandardsAdapter

log = logging.getLogger(__name__)

# PromoStandards WSDL endpoints, per the SanMar Web Services Integration
# Guide v24.3. All SanMar web services (legacy + PromoStandards) are served
# from ws.sanmar.com:8080 in production; test environment uses the same
# paths under test-ws.sanmar.com:8080. Set SANMAR_USE_TEST=1 in .env to
# target test (e.g. when Christian issues test-environment creds).
_SANMAR_HOST = (
    "test-ws.sanmar.com:8080"
    if os.getenv("SANMAR_USE_TEST", "0") == "1"
    else "ws.sanmar.com:8080"
)
SANMAR_WSDLS = {
    # Product Data Service v2.0.0 (guide p8)
    "PRODUCT":   f"https://{_SANMAR_HOST}/promostandards/ProductDataServiceBindingV2?WSDL",
    # Media Content Service v1.0.0 (guide p54)
    "MEDIA":     f"https://{_SANMAR_HOST}/promostandards/MediaContentServiceBinding?wsdl",
    # Pricing and Configuration Service v1.0.0 (guide p81)
    "PRICING":   f"https://{_SANMAR_HOST}/promostandards/PricingAndConfigurationServiceBinding?WSDL",
    # Inventory Service v2.0.0 (guide p67)
    "INVENTORY": f"https://{_SANMAR_HOST}/promostandards/InventoryServiceBindingV2final?WSDL",
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
