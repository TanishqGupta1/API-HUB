"""Asynchronous PromoStandards SOAP client.

zeep is synchronous. Every call is wrapped with ``asyncio.to_thread`` so it
cooperates with FastAPI's event loop. A single ``PromoStandardsClient`` instance
is tied to one WSDL (one service type). The caller constructs a new client per
service — product_data / inventory / ppc / media each have their own WSDL.

The WSDL is parse-cached on disk via ``zeep.cache.SqliteCache`` so subsequent
instances for the same URL skip re-parsing.

Response parsing is **deliberately defensive**. PromoStandards implementations
in the wild deviate from the spec (different casing, optional wrappers,
missing arrays). The walk helpers try several attribute paths before giving
up, and per-item parse errors are swallowed with a log rather than failing
the whole batch — one broken product should not abort a sync of 5000.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Iterable

from zeep import Client as ZeepClient
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

# PromoStandards caps inventory at 500 per the spec — anything larger is
# reported as exactly 500. Mirror that here so downstream callers don't have
# to special-case it.
_INVENTORY_CAP = 500


# ---------------------------------------------------------------------------
# zeep response walkers — tolerant of shape drift across PS implementations
# ---------------------------------------------------------------------------

def _attr(obj: Any, *names: str, default: Any = None) -> Any:
    """Return the first attribute in ``names`` that exists on ``obj``.

    zeep gives CamelCase, some suppliers return lowerCamelCase. Walk a short
    list of candidates rather than guess wrong.
    """
    if obj is None:
        return default
    if isinstance(obj, dict):
        for name in names:
            if name in obj:
                return obj[name]
        return default
    for name in names:
        value = getattr(obj, name, None)
        if value is not None:
            return value
    return default


def _as_list(value: Any) -> list[Any]:
    """Normalize a zeep single-item-or-list into a list."""
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def _text(value: Any) -> str | None:
    """Coerce to a non-empty string, or None."""
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ---------------------------------------------------------------------------
# PromoStandardsClient
# ---------------------------------------------------------------------------

class PromoStandardsClient:
    """SOAP adapter for one PromoStandards service endpoint.

    Parameters
    ----------
    wsdl_url: str
        Production WSDL URL resolved from the PS directory endpoint cache.
    auth_config: dict
        Credentials dict from ``Supplier.auth_config``. PS convention is
        ``{"id": "...", "password": "..."}``.
    service: zeep service proxy, optional
        Inject a pre-built service for tests. When provided the WSDL is not
        fetched or parsed.
    """

    def __init__(
        self,
        wsdl_url: str,
        auth_config: dict,
        *,
        service: Any | None = None,
    ) -> None:
        self.wsdl_url = wsdl_url
        self.auth_config = auth_config or {}
        self._service = service

    # -- zeep bootstrap ----------------------------------------------------

    def _get_service(self) -> Any:
        if self._service is not None:
            return self._service
        transport = Transport(cache=SqliteCache())
        self._service = ZeepClient(self.wsdl_url, transport=transport).service
        return self._service

    def _auth(self, ws_version: str) -> dict:
        return {
            "wsVersion": ws_version,
            "id": self.auth_config.get("id", ""),
            "password": self.auth_config.get("password", ""),
        }

    # -- Product Data ------------------------------------------------------

    async def get_sellable_product_ids(self, ws_version: str = "2.0.0") -> list[str]:
        return await asyncio.to_thread(self._sync_get_sellable_product_ids, ws_version)

    def _sync_get_sellable_product_ids(self, ws_version: str) -> list[str]:
        svc = self._get_service()
        response = svc.getProductSellable(**self._auth(ws_version))

        container = _attr(response, "ProductSellableArray", "productSellableArray")
        items = _as_list(_attr(container, "ProductSellable", "productSellable"))

        ids: list[str] = []
        for item in items:
            # Only include items that are actively sellable if the flag is set.
            # Absent flag == treat as sellable (some suppliers omit it).
            is_sellable = _attr(item, "isSellable", "sellable")
            if is_sellable is False:
                continue
            pid = _text(_attr(item, "productId", "product_id"))
            if pid:
                ids.append(pid)
        return ids

    async def get_product(
        self,
        product_id: str,
        ws_version: str = "2.0.0",
        localization_country: str = "us",
        localization_language: str = "en",
    ) -> PSProductData | None:
        return await asyncio.to_thread(
            self._sync_get_product,
            product_id,
            ws_version,
            localization_country,
            localization_language,
        )

    def _sync_get_product(
        self,
        product_id: str,
        ws_version: str,
        localization_country: str,
        localization_language: str,
    ) -> PSProductData | None:
        svc = self._get_service()
        try:
            response = svc.getProduct(
                productId=product_id,
                localizationCountry=localization_country,
                localizationLanguage=localization_language,
                **self._auth(ws_version),
            )
        except Exception as exc:  # noqa: BLE001 — defensive: per-product failure isolation
            log.warning("getProduct(%s) failed: %s", product_id, exc)
            return None
        return self._parse_product(response)

    async def get_products_batch(
        self,
        product_ids: list[str],
        batch_size: int = 50,
        ws_version: str = "2.0.0",
        localization_country: str = "us",
        localization_language: str = "en",
    ) -> list[PSProductData]:
        """Fetch products in batches. Batch size is advisory — PS getProduct is
        one-at-a-time, so the batches only govern how often we yield to the
        loop."""
        out: list[PSProductData] = []
        for i in range(0, len(product_ids), batch_size):
            batch = product_ids[i : i + batch_size]
            results = await asyncio.to_thread(
                self._sync_fetch_batch,
                batch,
                ws_version,
                localization_country,
                localization_language,
            )
            out.extend(results)
        return out

    def _sync_fetch_batch(
        self,
        product_ids: list[str],
        ws_version: str,
        localization_country: str,
        localization_language: str,
    ) -> list[PSProductData]:
        svc = self._get_service()
        out: list[PSProductData] = []
        for pid in product_ids:
            try:
                response = svc.getProduct(
                    productId=pid,
                    localizationCountry=localization_country,
                    localizationLanguage=localization_language,
                    **self._auth(ws_version),
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("getProduct(%s) failed: %s", pid, exc)
                continue
            parsed = self._parse_product(response)
            if parsed is not None:
                out.append(parsed)
        return out

    def _parse_product(self, response: Any) -> PSProductData | None:
        product = _attr(response, "Product", "product") or response
        pid = _text(_attr(product, "productId", "product_id"))
        if not pid:
            return None

        cat_container = _attr(product, "ProductCategoryArray", "productCategoryArray")
        category_items = _as_list(_attr(cat_container, "ProductCategory", "productCategory"))
        categories: list[str] = []
        for c in category_items:
            # Category element can be a wrapper with .productCategory, or the
            # raw string directly if the array holds primitives.
            name = _text(_attr(c, "productCategory", "name")) or _text(c)
            if name:
                categories.append(name)

        parts_container = _attr(product, "productPartArray", "ProductPartArray")
        part_items = _as_list(_attr(parts_container, "productPart", "ProductPart"))
        parts = [p for p in (self._parse_part(item) for item in part_items) if p]

        return PSProductData(
            product_id=pid,
            product_name=_text(_attr(product, "productName", "name")),
            description=_text(_attr(product, "description")),
            brand=_text(_attr(product, "productBrand", "brand")),
            categories=categories,
            product_type=_text(_attr(product, "productType")) or "apparel",
            primary_image_url=_text(_attr(product, "primaryImageURL", "primaryImageUrl")),
            parts=parts,
        )

    def _parse_part(self, item: Any) -> PSProductPart | None:
        part_id = _text(_attr(item, "partId", "part_id"))
        if not part_id:
            return None

        color_container = _attr(item, "ColorArray", "colorArray")
        color_items = _as_list(_attr(color_container, "Color", "color"))
        color_name = None
        for c in color_items:
            color_name = _text(_attr(c, "colorName", "name")) or _text(c)
            if color_name:
                break

        size_container = _attr(item, "ApparelSize", "apparelSize")
        size_name = _text(_attr(size_container, "labelSize", "apparelStyle", "numericSize"))

        return PSProductPart(
            part_id=part_id,
            color_name=color_name,
            size_name=size_name,
            description=_text(_attr(item, "description")),
        )

    # -- Inventory ---------------------------------------------------------

    async def get_inventory(
        self, product_ids: list[str], ws_version: str = "2.0.0"
    ) -> list[PSInventoryLevel]:
        return await asyncio.to_thread(
            self._sync_get_inventory, product_ids, ws_version
        )

    def _sync_get_inventory(
        self, product_ids: list[str], ws_version: str
    ) -> list[PSInventoryLevel]:
        svc = self._get_service()
        out: list[PSInventoryLevel] = []
        for pid in product_ids:
            try:
                response = svc.getInventoryLevels(
                    productId=pid, **self._auth(ws_version)
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("getInventoryLevels(%s) failed: %s", pid, exc)
                continue
            out.extend(self._parse_inventory(response, pid))
        return out

    def _parse_inventory(self, response: Any, product_id: str) -> Iterable[PSInventoryLevel]:
        inv_root = _attr(response, "Inventory", "inventory") or response
        for inv_record in _as_list(inv_root):
            rec_pid = _text(_attr(inv_record, "productId")) or product_id
            parts_container = _attr(
                inv_record, "PartInventoryArray", "partInventoryArray"
            )
            part_items = _as_list(_attr(parts_container, "PartInventory", "partInventory"))
            for part in part_items:
                part_id = _text(_attr(part, "partId", "part_id"))
                if not part_id:
                    continue
                raw_qty = _attr(part, "quantityAvailable", "quantity")
                qty = self._coerce_int(raw_qty)
                # Spec caps at 500 — enforce it here so callers never see more.
                qty = min(qty, _INVENTORY_CAP)

                warehouse = None
                loc_container = _attr(
                    part, "InventoryLocationArray", "inventoryLocationArray"
                )
                locs = _as_list(_attr(loc_container, "InventoryLocation", "inventoryLocation"))
                if locs:
                    warehouse = _text(
                        _attr(locs[0], "inventoryLocationName", "name")
                    )

                yield PSInventoryLevel(
                    product_id=rec_pid,
                    part_id=part_id,
                    quantity_available=qty,
                    warehouse_code=warehouse,
                )

    @staticmethod
    def _coerce_int(value: Any) -> int:
        if value is None:
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            try:
                return int(float(value))
            except (TypeError, ValueError):
                return 0

    # -- Pricing (PPC) -----------------------------------------------------

    async def get_pricing(
        self, product_ids: list[str], ws_version: str = "1.0.0"
    ) -> list[PSPricePoint]:
        return await asyncio.to_thread(self._sync_get_pricing, product_ids, ws_version)

    def _sync_get_pricing(
        self, product_ids: list[str], ws_version: str
    ) -> list[PSPricePoint]:
        svc = self._get_service()
        out: list[PSPricePoint] = []
        for pid in product_ids:
            try:
                response = svc.getConfigurationAndPricing(
                    productId=pid, **self._auth(ws_version)
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("getConfigurationAndPricing(%s) failed: %s", pid, exc)
                continue
            out.extend(self._parse_pricing(response, pid))
        return out

    def _parse_pricing(self, response: Any, product_id: str) -> Iterable[PSPricePoint]:
        config = _attr(response, "Configuration", "configuration") or response
        parts_container = _attr(config, "PartArray", "partArray")
        parts = _as_list(_attr(parts_container, "Part", "part"))
        for part in parts:
            part_id = _text(_attr(part, "partId", "part_id"))
            if not part_id:
                continue
            price_container = _attr(part, "PartPriceArray", "partPriceArray")
            prices = _as_list(_attr(price_container, "PartPrice", "partPrice"))
            for pp in prices:
                price_raw = _attr(pp, "price", "Price")
                if price_raw is None:
                    continue
                try:
                    price_value = float(price_raw)
                except (TypeError, ValueError):
                    continue
                qty_min = self._coerce_int(_attr(pp, "minQuantity", "quantityMin")) or 1
                qty_max_raw = _attr(pp, "maxQuantity", "quantityMax")
                qty_max = self._coerce_int(qty_max_raw) if qty_max_raw is not None else None
                price_type = _text(_attr(pp, "priceType", "type")) or "piece"
                yield PSPricePoint(
                    product_id=product_id,
                    part_id=part_id,
                    price=price_value,
                    quantity_min=qty_min,
                    quantity_max=qty_max,
                    price_type=price_type,
                )

    # -- Media Content -----------------------------------------------------

    async def get_media(
        self, product_ids: list[str], ws_version: str = "1.0.0"
    ) -> list[PSMediaItem]:
        return await asyncio.to_thread(self._sync_get_media, product_ids, ws_version)

    def _sync_get_media(
        self, product_ids: list[str], ws_version: str
    ) -> list[PSMediaItem]:
        svc = self._get_service()
        out: list[PSMediaItem] = []
        for pid in product_ids:
            try:
                response = svc.getMediaContent(productId=pid, **self._auth(ws_version))
            except Exception as exc:  # noqa: BLE001
                log.warning("getMediaContent(%s) failed: %s", pid, exc)
                continue
            out.extend(self._parse_media(response, pid))
        return out

    def _parse_media(self, response: Any, product_id: str) -> Iterable[PSMediaItem]:
        media_container = _attr(response, "MediaContentArray", "mediaContentArray")
        items = _as_list(_attr(media_container, "MediaContent", "mediaContent"))
        for item in items:
            url = _text(_attr(item, "url", "URL", "mediaUrl"))
            if not url:
                continue
            yield PSMediaItem(
                product_id=_text(_attr(item, "productId")) or product_id,
                url=url,
                media_type=_text(_attr(item, "mediaType", "type")) or "front",
                color_name=_text(_attr(item, "color", "colorName")),
            )
