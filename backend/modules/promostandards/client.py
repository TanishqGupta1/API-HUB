"""PromoStandardsClient — zeep SOAP wrapper for any PS-compliant supplier.

zeep is synchronous. Every service call is wrapped in ``asyncio.to_thread``
so the FastAPI event loop is never blocked during a long-running sync.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from zeep import Client, Settings
from zeep.cache import SqliteCache
from zeep.transports import Transport

from .schemas import (
    PSInventoryLevel,
    PSMediaItem,
    PSPricePoint,
    PSProductData,
    PSProductPart,
)

log = logging.getLogger(__name__)

# Shared WSDL cache — zeep parses WSDLs once per process+URL.
_WSDL_CACHE = SqliteCache(timeout=86400)  # 24h


def _get(obj: Any, *path: str, default: Any = None) -> Any:
    """Safely drill into nested zeep objects using dotted paths."""
    cur = obj
    for key in path:
        if cur is None:
            return default
        cur = getattr(cur, key, None)
    return cur if cur is not None else default


def _iter_array(array_wrapper: Any, item_attr: str) -> list[Any]:
    """PS responses wrap lists as `<FooArray><Foo>...</Foo><Foo>...</Foo></FooArray>`.

    Return the inner list, or [] if the wrapper is None.
    """
    if array_wrapper is None:
        return []
    inner = getattr(array_wrapper, item_attr, None)
    if inner is None:
        return []
    return inner if isinstance(inner, list) else [inner]


class PromoStandardsClient:
    """SOAP client for any PromoStandards supplier endpoint."""

    def __init__(self, wsdl_url: str, credentials: dict):
        self._wsdl_url = wsdl_url
        self._credentials = credentials
        transport = Transport(cache=_WSDL_CACHE, timeout=30)
        settings = Settings(strict=False, xml_huge_tree=True)
        self._client = Client(wsdl_url, transport=transport, settings=settings)

    # ------------- public methods -------------

    async def get_sellable_product_ids(self, ws_version: str = "2.0.0") -> list[str]:
        """Return all active supplier product IDs."""
        try:
            resp = await asyncio.to_thread(
                self._client.service.getProductSellable,
                wsVersion=ws_version,
                **self._credentials,
            )
            items = _iter_array(_get(resp, "ProductSellableArray"), "ProductSellable")
            return [str(_get(i, "productId", default="")) for i in items if _get(i, "productId")]
        except Exception as e:
            log.error("getProductSellable failed: %s", e)
            return []

    async def get_product_date_modified(
        self, since: str, ws_version: str = "1.0.0"
    ) -> list[str]:
        """Return IDs of products modified since the given ISO timestamp."""
        try:
            resp = await asyncio.to_thread(
                self._client.service.getProductDateModified,
                wsVersion=ws_version,
                lastUpdatedTimestamp=since,
                **self._credentials,
            )
            items = _iter_array(_get(resp, "ProductDateModifiedArray"), "ProductDateModified")
            return [str(_get(i, "productId", default="")) for i in items if _get(i, "productId")]
        except Exception as e:
            log.error("getProductDateModified failed: %s", e)
            return []

    async def get_product(self, product_id: str, ws_version: str = "1.0.0") -> PSProductData:
        """Return one product with its color/size parts."""
        resp = await asyncio.to_thread(
            self._client.service.getProduct,
            wsVersion="1.0.0", # Most suppliers use 1.0.0 for Product Data
            productId=product_id,
            **self._credentials,
        )
        return self._parse_product(_get(resp, "Product"))

    async def get_products_batch(
        self, product_ids: list[str], batch_size: int = 50
    ) -> list[PSProductData]:
        """Fetch products one at a time (per PS spec) but in batched chunks.

        Individual product failures are logged and skipped so one bad SKU
        doesn't abort a full catalog sync.
        """
        results: list[PSProductData] = []
        for start in range(0, len(product_ids), batch_size):
            chunk = product_ids[start : start + batch_size]
            for pid in chunk:
                try:
                    results.append(await self.get_product(pid))
                except Exception as exc:  # noqa: BLE001
                    log.warning("get_product(%s) failed: %s", pid, exc)
        return results

    async def get_inventory(
        self, product_ids: list[str], ws_version: str = "2.0.0"
    ) -> list[PSInventoryLevel]:
        """Return part-level inventory for the given products."""
        levels: list[PSInventoryLevel] = []
        for pid in product_ids:
            try:
                resp = await asyncio.to_thread(
                    self._client.service.getInventoryLevels,
                    wsVersion=ws_version,
                    productId=pid,
                    **self._credentials,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("getInventoryLevels(%s) failed: %s", pid, exc)
                continue
            parts = _iter_array(
                _get(resp, "Inventory", "ProductVariationInventoryArray"),
                "ProductVariationInventory",
            )
            for part in parts:
                locations = _iter_array(
                    _get(part, "InventoryLocationArray"), "InventoryLocation"
                )
                warehouse = (
                    str(_get(locations[0], "inventoryLocationId", default="")) if locations else None
                )
                qty = int(_get(part, "quantityAvailable", "Quantity", "value", default=0) or 0)
                levels.append(
                    PSInventoryLevel(
                        product_id=pid,
                        part_id=str(_get(part, "partId", default="")),
                        quantity_available=min(qty, 500),
                        warehouse_code=warehouse,
                    )
                )
        return levels

    # ------------- parsers -------------

    def _parse_product(self, raw: Any) -> PSProductData:
        if raw is None:
            raise ValueError("Parsed product is None")
            
        categories = [
            str(_get(c, "categoryName", default=""))
            for c in _iter_array(_get(raw, "ProductCategoryArray"), "ProductCategory")
        ]
        parts = [self._parse_part(p) for p in _iter_array(_get(raw, "ProductPartArray"), "ProductPart")]
        return PSProductData(
            product_id=str(_get(raw, "productId", default="")),
            product_name=_get(raw, "productName"),
            description=_get(raw, "description"),
            brand=_get(raw, "ProductBrand"),
            categories=[c for c in categories if c],
            primary_image_url=_get(raw, "primaryImageURL"),
            parts=parts,
        )

    def _parse_part(self, raw: Any) -> PSProductPart:
        colors = _iter_array(_get(raw, "ColorArray"), "Color")
        color_name = _get(colors[0], "colorName") if colors else None
        size_name = _get(raw, "ApparelSize", "labelSize")
        return PSProductPart(
            part_id=str(_get(raw, "partId", default="")),
            color_name=color_name,
            size_name=size_name,
            description=_get(raw, "description"),
        )
