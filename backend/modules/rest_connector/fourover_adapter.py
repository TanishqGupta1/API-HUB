"""FourOverAdapter — wires FourOverClient into the BaseAdapter registry.

4Over uses REST + HMAC-SHA256 auth. This adapter bridges the existing
FourOverClient (HTTP calls) into the Phase 2 BaseAdapter interface so
the import_jobs orchestrator can drive it identically to OPSAdapter.

Credentials come from supplier.auth_config (encrypted):
    {"api_key": "...", "private_key": "..."}

Product type is always "print" for 4Over (print products only).
DELTA mode is not supported by 4Over's API — falls back to full discovery.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import httpx

from modules.catalog.schemas import (
    OptionAttributeIngest,
    OptionIngest,
    PrintDetailsIngest,
    ProductIngest,
    ProductSizeIngest,
)
from modules.import_jobs.base import (
    AuthError,
    BaseAdapter,
    DiscoveryMode,
    ProductRef,
    SupplierError,
    TransientError,
)
from modules.import_jobs.registry import register_adapter

from .fourover_client import FourOverClient


class FourOverAdapter(BaseAdapter):
    """Adapter for the 4Over REST + HMAC API."""

    def __init__(self, supplier, db):
        super().__init__(supplier, db)
        auth = supplier.auth_config or {}
        if not auth.get("api_key") or not auth.get("private_key"):
            raise AuthError(
                f"supplier {supplier.name!r} missing api_key or private_key in auth_config"
            )
        base_url = supplier.base_url or "https://sandbox-api.4over.com"
        self.client = FourOverClient(base_url=base_url, auth_config=auth)

    async def discover(
        self,
        mode: DiscoveryMode,
        *,
        limit: Optional[int] = None,
        explicit_list: Optional[list[str]] = None,
    ) -> list[ProductRef]:
        if mode == DiscoveryMode.EXPLICIT_LIST:
            if not explicit_list:
                raise ValueError("EXPLICIT_LIST mode requires explicit_list")
            return [ProductRef(supplier_sku=str(s)) for s in explicit_list]

        # 4Over has no modified-since endpoint — DELTA falls back to full
        try:
            products = await self.client.get_products()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise AuthError(f"4Over auth failed: {e}", code=str(e.response.status_code))
            raise TransientError(f"4Over API error: {e}", code=str(e.response.status_code))
        except httpx.RequestError as e:
            raise TransientError(f"4Over network error: {e}")

        refs = [
            ProductRef(supplier_sku=str(p.get("uuid") or p.get("id") or i))
            for i, p in enumerate(products)
            if isinstance(p, dict)
        ]

        if mode == DiscoveryMode.FIRST_N and limit is not None:
            refs = refs[:limit]

        return refs

    async def hydrate_product(self, ref: ProductRef) -> ProductIngest:
        try:
            options_data = await self.client.get_product_options(ref.supplier_sku)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SupplierError(
                    f"4Over product {ref.supplier_sku} not found", code="404"
                )
            raise TransientError(f"4Over API error: {e}", code=str(e.response.status_code))
        except httpx.RequestError as e:
            raise TransientError(f"4Over network error: {e}")

        return self._normalize(ref.supplier_sku, options_data)

    def _normalize(self, product_uuid: str, raw: dict) -> ProductIngest:
        """Map raw 4Over option-groups response → ProductIngest (print type)."""
        product_name = raw.get("name") or raw.get("product_name") or f"4Over {product_uuid}"
        description = raw.get("description")
        brand = raw.get("brand") or "4Over"

        # Build print_details from size constraints if present
        constraints = raw.get("size_constraints") or {}
        print_details = PrintDetailsIngest(
            pricing_method="formula",
            min_width=constraints.get("min_width"),
            max_width=constraints.get("max_width"),
            min_height=constraints.get("min_height"),
            max_height=constraints.get("max_height"),
            size_unit=constraints.get("unit", "in"),
        )

        # Build preset sizes from size_options if available
        sizes: list[ProductSizeIngest] = []
        for sz in raw.get("size_options") or []:
            if isinstance(sz, dict) and sz.get("width") and sz.get("height"):
                sizes.append(
                    ProductSizeIngest(
                        width=sz["width"],
                        height=sz["height"],
                        unit=sz.get("unit", "in"),
                        label=sz.get("label"),
                    )
                )

        # Map option groups to OptionIngest
        options: list[OptionIngest] = []
        for i, group in enumerate(raw.get("option_groups") or []):
            if not isinstance(group, dict):
                continue
            attributes = [
                OptionAttributeIngest(
                    title=str(attr.get("name") or attr.get("title") or ""),
                    sort_order=j,
                    multiplier=str(attr.get("price_multiplier") or "1.00"),
                )
                for j, attr in enumerate(group.get("options") or [])
                if isinstance(attr, dict)
            ]
            options.append(
                OptionIngest(
                    option_key=str(group.get("id") or group.get("key") or f"option_{i}"),
                    title=str(group.get("name") or group.get("title") or ""),
                    options_type="radio",
                    sort_order=i,
                    attributes=attributes,
                )
            )

        return ProductIngest(
            supplier_sku=product_uuid,
            product_name=product_name,
            brand=brand,
            description=description,
            product_type="print",
            print_details=print_details,
            sizes=sizes,
            options=options,
        )

    async def discover_changed(self, since: datetime) -> list[ProductRef]:
        # 4Over has no modified-since endpoint — return all sellable products
        return await self.discover(DiscoveryMode.FULL_SELLABLE)


register_adapter("FourOverAdapter", FourOverAdapter)
