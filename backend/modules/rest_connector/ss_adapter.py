"""S&S Activewear REST adapter.

S&S uses a JSON REST API (not SOAP). Auth is HTTP Basic with
account_number:api_key. Products are grouped by styleID.

Credentials in auth_config: {"account_number": "...", "api_key": "..."}

DELTA mode is not supported by S&S — falls back to full discovery.
"""
from __future__ import annotations

from typing import Optional
from decimal import Decimal

import httpx

from modules.catalog.schemas import (
    ApparelDetailsIngest,
    ImageIngest,
    ProductIngest,
    VariantIngest,
    VariantPriceIngest,
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

from .ss_normalizer import ss_to_ps_format

_DEFAULT_BASE_URL = "https://api.ssactivewear.com/v2"


def _ps_product_to_ingest(ps_product, inventories, prices, media) -> ProductIngest:
    """Convert PSProductData + related data → ProductIngest."""
    sku_to_price: dict[str, list[VariantPriceIngest]] = {}
    for p in prices:
        sku_to_price.setdefault(p.part_id, []).append(
            VariantPriceIngest(
                price_type=p.price_type,
                quantity_min=p.quantity_min,
                price=Decimal(str(p.price)),
            )
        )

    sku_to_inventory: dict[str, int] = {
        inv.part_id: inv.quantity_available for inv in inventories
        if inv.product_id == ps_product.product_id
    }

    variants = [
        VariantIngest(
            part_id=part.part_id,
            sku=part.part_id,
            color=part.color_name,
            size=part.size_name,
            inventory=sku_to_inventory.get(part.part_id),
            prices=sku_to_price.get(part.part_id, []),
        )
        for part in ps_product.parts
    ]

    images = [
        ImageIngest(url=m.url, image_type=m.media_type, color=m.color_name)
        for m in media
        if m.product_id == ps_product.product_id
    ]
    if not images and ps_product.primary_image_url:
        images = [ImageIngest(url=ps_product.primary_image_url, image_type="front")]

    category_name = ps_product.categories[0] if ps_product.categories else None

    return ProductIngest(
        supplier_sku=ps_product.product_id,
        product_name=ps_product.product_name or ps_product.product_id,
        brand=ps_product.brand,
        description=ps_product.description,
        product_type="apparel",
        category_name=category_name,
        category_external_id=category_name,
        variants=variants,
        images=images,
        apparel_details=ApparelDetailsIngest(pricing_method="tiered_variants"),
    )


class SSAdapter(BaseAdapter):
    """Adapter for S&S Activewear REST API."""

    def __init__(self, supplier, db):
        super().__init__(supplier, db)
        auth = supplier.auth_config or {}
        account = auth.get("account_number")
        api_key = auth.get("api_key")
        if not account or not api_key:
            raise AuthError(
                f"supplier {supplier.name!r} missing account_number or api_key in auth_config"
            )
        base_url = (supplier.base_url or _DEFAULT_BASE_URL).rstrip("/")
        self._client = httpx.AsyncClient(
            base_url=base_url,
            auth=(account, api_key),
            headers={"Accept": "application/json"},
            timeout=30.0,
        )

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

        # S&S has no modified-since endpoint — DELTA falls back to full
        try:
            resp = await self._client.get("/styles/", params={"fields": "styleID"})
            resp.raise_for_status()
            styles = resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (401, 403):
                raise AuthError(f"S&S auth failed: {e}", code=str(e.response.status_code))
            raise TransientError(f"S&S API error: {e}", code=str(e.response.status_code))
        except httpx.RequestError as e:
            raise TransientError(f"S&S network error: {e}")

        refs = [
            ProductRef(supplier_sku=str(s.get("styleID") or s.get("id") or i))
            for i, s in enumerate(styles)
            if isinstance(s, dict) and (s.get("styleID") or s.get("id"))
        ]

        if mode == DiscoveryMode.FIRST_N and limit is not None:
            refs = refs[:limit]

        return refs

    async def hydrate_product(self, ref: ProductRef) -> ProductIngest:
        try:
            resp = await self._client.get(
                "/products/", params={"styleID": ref.supplier_sku}
            )
            resp.raise_for_status()
            rows = resp.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise SupplierError(
                    f"S&S style {ref.supplier_sku} not found", code="404"
                )
            if e.response.status_code in (401, 403):
                raise AuthError(f"S&S auth failed: {e}", code=str(e.response.status_code))
            raise TransientError(f"S&S API error: {e}", code=str(e.response.status_code))
        except httpx.RequestError as e:
            raise TransientError(f"S&S network error: {e}")

        if not rows:
            raise SupplierError(f"S&S style {ref.supplier_sku} returned no rows", code="empty")

        products, inventories, prices, media = ss_to_ps_format(rows)
        if not products:
            raise SupplierError(
                f"S&S normalizer returned no products for style {ref.supplier_sku}",
                code="normalize_empty",
            )

        return _ps_product_to_ingest(products[0], inventories, prices, media)

    async def discover_changed(self, since) -> list[ProductRef]:
        # S&S has no modified-since endpoint — return full list
        return await self.discover(DiscoveryMode.FULL)


register_adapter("SSAdapter", SSAdapter)
