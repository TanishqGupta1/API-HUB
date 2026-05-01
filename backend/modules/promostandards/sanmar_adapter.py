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

SANMAR_WSDLS = {
    "PRODUCT": "https://promostandards.sanmar.com/ProductDataService/v200?wsdl",
    "MEDIA": "https://promostandards.sanmar.com/MediaService/v110?wsdl",
    "PRICING": "https://promostandards.sanmar.com/PricingAndConfigurationService/v100?wsdl",
    "INVENTORY": "https://promostandards.sanmar.com/InventoryService/v200?wsdl",
}


class SanMarAdapter(PromoStandardsAdapter):
    """Subclass for SanMar that uses hardcoded WSDLs and special auth."""

    def _wsdl_for(self, service_type: str) -> str:
        url = SANMAR_WSDLS.get(service_type.upper())
        if url:
            return url
        return super()._wsdl_for(service_type)

    def _require_auth(self) -> dict:
        """SanMar sometimes needs additional fields in auth_config.
        
        We normalize them to 'id' and 'password' for the base adapter,
        but SanMar specific calls might need more.
        """
        auth = super()._require_auth()
        # SanMar auth is standard PS id/password for PS endpoints.
        return auth

# Self-register
register_adapter("SanMarAdapter", SanMarAdapter)
