"""Asynchronous PromoStandards SOAP client.

zeep is synchronous. Every call is wrapped with ``asyncio.to_thread`` so it
cooperates with FastAPI's event loop. A single ``PromoStandardsClient`` instance
is tied to one WSDL (one service type). The caller constructs a new client per
service — product_data / inventory / ppc / media each have their own WSDL.

WSDL caching strategy
---------------------
* Default: ``zeep.cache.InMemoryCache`` — survives within a process restart but
  not across container restarts.  Zero filesystem dependency, safe in Docker.
* Optional: set ``WSDL_CACHE_DIR`` env var to a directory mounted as a Docker
  volume.  The client then uses ``zeep.cache.SqliteCache(path=…)`` so the
  parsed WSDL survives container restarts.

The previous default of ``SqliteCache()`` (no path → ``/tmp`` inside the
container) was lost on every container restart, giving the worst of both
worlds: slow on every cold start AND no persistence.

Response parsing is **deliberately defensive**. PromoStandards implementations
in the wild deviate from the spec (different casing, optional wrappers,
missing arrays). The walk helpers try several attribute paths before giving
up, and per-item parse errors are swallowed with a log rather than failing
the whole batch — one broken product should not abort a sync of 5000.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Iterable

from zeep import Client as ZeepClient
from zeep.transports import Transport

from .schemas import (
    PSCategoryData,
    PSInventoryLevel,
    PSMediaItem,
    PSPricePoint,
    PSProductData,
    PSProductPart,
)

# SanMar's `getProductInfoByCategory` lives on a SanMar-specific SOAP service,
# NOT on the standard PromoStandards ProductData binding. The PS directory's
# endpoint cache doesn't know about it — use this constant when the caller is
# SanMar (supplier.promostandards_code == "SANMAR").
SANMAR_EXT_WSDL = (
    "https://ws.sanmar.com:8080/SanMarWebService/SanMarProductInfoServicePort?wsdl"
)

# SanMar ships a fixed category list in their Web Services Integration Guide
# (sanmar/SanMar-Web-Services-Integration-Guide-24.3.pdf p25-33). Not a SOAP
# endpoint — just the strings their `getProductInfoByCategory` accepts.
SANMAR_CATEGORIES = [
    "Accessories", "Activewear", "Bags", "Caps", "Golf Shirts", 
    "Headwear", "Infant & Toddler", "Outerwear", 
    "Pants & Shorts", "Performance", "Polos/Knits", "Safety", 
    "Sweatshirts/Fleece", "T-Shirts", "Tall", "Woven Shirts", 
    "Youth", "Shoes", "Scrubs",
]

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WSDL cache factory

def _build_wsdl_cache():
    """Return the best available zeep cache object.

    Checks ``WSDL_CACHE_DIR`` env var:
    - Set → SqliteCache stored in that directory (mount a Docker volume there
      for persistence across container restarts).
    - Unset → InMemoryCache (process-lifetime cache; no filesystem dependency).
    """
    cache_dir = os.getenv("WSDL_CACHE_DIR", "").strip()
    if cache_dir:
        from zeep.cache import SqliteCache
        os.makedirs(cache_dir, exist_ok=True)
        cache_path = os.path.join(cache_dir, "wsdl.db")
        log.debug("WSDL cache: SqliteCache at %s", cache_path)
        return SqliteCache(path=cache_path)
    from zeep.cache import InMemoryCache
    log.debug("WSDL cache: InMemoryCache (process-lifetime)")
    return InMemoryCache()


# Module-level singleton — one cache shared across all client instances so
# a WSDL fetched by one supplier request benefits all subsequent ones.
_WSDL_CACHE = _build_wsdl_cache()


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
        self._history = None

    # -- zeep bootstrap ----------------------------------------------------

    def _get_service(self) -> Any:
        return self.get_service_with_history()[0]

    def get_service_with_history(self) -> tuple[Any, Any]:
        """Return (service, history_plugin). History allows raw XML access."""
        if self._service is not None:
            # An injected service (typically a test fake) shouldn't need to
            # spin up zeep; lazily attach a HistoryPlugin only when callers
            # actually need history. The plugin has no side-effects when not
            # wired into a zeep client.
            if self._history is None:
                from zeep.plugins import HistoryPlugin
                self._history = HistoryPlugin()
            return self._service, self._history

        from zeep.settings import Settings
        from zeep.plugins import HistoryPlugin
        settings = Settings(strict=False, xml_huge_tree=True)
        transport = Transport(
            cache=_WSDL_CACHE, timeout=30, operation_timeout=120
        )
        self._history = HistoryPlugin()

        try:
            client = ZeepClient(
                self.wsdl_url, 
                transport=transport, 
                settings=settings,
                plugins=[self._history]
            )
            self._service = client.service
        except ValueError as e:
            if "no default service defined" in str(e).lower() and "?wsdl" not in self.wsdl_url.lower():
                retry_url = self.wsdl_url + ("&wsdl" if "?" in self.wsdl_url else "?wsdl")
                log.info("No default service at %s, retrying with %s", self.wsdl_url, retry_url)
                client = ZeepClient(
                    retry_url, 
                    transport=transport, 
                    settings=settings,
                    plugins=[self._history]
                )
                self._service = client.service
            else:
                raise
        
        return self._service, self._history

    def _auth(
        self,
        ws_version: str,
        localization_country: str | None = None,
        localization_language: str | None = None,
    ) -> dict:
        payload = {
            "wsVersion": ws_version,
            "id": self.auth_config.get("id", ""),
            "password": self.auth_config.get("password", ""),
        }
        if localization_country is not None:
            payload["localizationCountry"] = localization_country
        if localization_language is not None:
            payload["localizationLanguage"] = localization_language
        return payload

    # -- Product Data ------------------------------------------------------

    async def get_sellable_product_ids(self, ws_version: str = "2.0.0") -> list[str]:
        return await asyncio.to_thread(self._sync_get_sellable_product_ids, ws_version)

    def _sync_get_sellable_product_ids(self, ws_version: str) -> list[str]:
        svc = self._get_service()
        response = svc.getProductSellable(isSellable=True, **self._auth(ws_version))

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
                **self._auth(ws_version, localization_country, localization_language),
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
                    **self._auth(ws_version, localization_country, localization_language),
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
            # SanMar uses <category>; others use <categoryName> or <productCategory>.
            # Fall back to raw string if the element itself is a primitive.
            name = _text(
                _attr(c, "category", "categoryName", "productCategory", "name")
            ) or _text(c)
            if name:
                categories.append(name)

        # description may be a list (SanMar emits one element per line) or a
        # single string. Join lists with newlines.
        raw_description = _attr(product, "description")
        if isinstance(raw_description, list):
            parts_desc = [_text(d) for d in raw_description]
            description = "\n".join(p for p in parts_desc if p) or None
        else:
            description = _text(raw_description)

        parts_container = _attr(product, "productPartArray", "ProductPartArray")
        part_items = _as_list(_attr(parts_container, "productPart", "ProductPart"))
        parts = [p for p in (self._parse_part(item) for item in part_items) if p]

        return PSProductData(
            product_id=pid,
            product_name=_text(_attr(product, "productName", "name")),
            description=description,
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

    # -- Categories (SanMar extension; not in PS spec) ---------------------

    async def get_categories(self) -> list[PSCategoryData]:
        """Return the supplier's browseable category list.

        SanMar: returns the fixed list from SANMAR_CATEGORIES (no SOAP call —
        their Integration Guide publishes it as a static list). Other suppliers
        raise NotImplementedError unless they override.
        """
        return [PSCategoryData(name=c) for c in SANMAR_CATEGORIES]

    async def get_products_by_category_productdata(
        self,
        category_name: str,
        limit: int = 10,
        scan_cap: int = 400,
        concurrency: int = 8,
        ws_version: str = "2.0.0",
        localization_country: str = "us",
        localization_language: str = "en",
    ) -> list[PSProductData]:
        """Fetch up to ``limit`` products in ``category_name`` using the standard
        PromoStandards ProductData service (fully inline).

        Avoids SanMar's ``getProductInfoByCategory`` extension, which for bulk
        categories returns no inline rows and instead drops a file on SanMar's
        SFTP server ("SanMarPI folder"). Here we pull the sellable product IDs
        (inline), then fetch product detail and keep the ones whose
        ``ProductCategoryArray`` matches ``category_name``. Scanning is bounded
        by ``scan_cap`` getProduct lookups so a sparse category can't run away.

        getProduct is one-at-a-time SOAP, so detail lookups run in waves of
        ``concurrency`` with an early exit once ``limit`` matches are found.
        """
        ids = await self.get_sellable_product_ids(ws_version)

        # getProductSellable returns one row per sellable part, so a style
        # repeats many times. Dedupe to unique product IDs, preserving order.
        seen: set[str] = set()
        unique: list[str] = []
        for pid in ids:
            if pid not in seen:
                seen.add(pid)
                unique.append(pid)

        target = category_name.strip().lower()
        candidates = unique[:scan_cap]
        out: list[PSProductData] = []

        for i in range(0, len(candidates), concurrency):
            if len(out) >= limit:
                break
            chunk = candidates[i : i + concurrency]
            results = await asyncio.gather(
                *[
                    self.get_product(
                        pid, ws_version, localization_country, localization_language
                    )
                    for pid in chunk
                ]
            )
            for prod in results:
                if prod and any(target in c.strip().lower() for c in prod.categories):
                    out.append(prod)
                    if len(out) >= limit:
                        break

        log.info(
            "ProductData category fetch(%s): scanned up to %d styles, matched %d (limit=%d)",
            category_name, min(len(candidates), len(unique)), len(out), limit,
        )
        return out[:limit]

    async def get_products_by_category(
        self,
        category_name: str,
        limit: int = 50,
        ws_version: str = "2.0.0",
        localization_country: str = "us",
        localization_language: str = "en",
        extension_wsdl_url: str | None = None,
    ) -> list[PSProductData]:
        """Call SanMar's getProductInfoByCategory, return first ``limit`` products.

        ``getProductInfoByCategory`` is a SanMar non-PS extension — it is NOT on
        the standard PromoStandards ProductData WSDL. For SanMar, pass
        ``extension_wsdl_url=SANMAR_EXT_WSDL``; a dedicated zeep client is spun
        up for this call. Without the override we attempt the call on the
        client's existing service and fail fast if the operation is missing.
        """
        return await asyncio.to_thread(
            self._sync_get_products_by_category,
            category_name,
            limit,
            ws_version,
            localization_country,
            localization_language,
            extension_wsdl_url,
        )

    def _sync_get_products_by_category(
        self,
        category_name: str,
        limit: int,
        ws_version: str,
        localization_country: str,
        localization_language: str,
        extension_wsdl_url: str | None,
    ) -> list[PSProductData]:
        if extension_wsdl_url:
            # SanMar-style extension — spin up a fresh zeep client for the
            # dedicated SanMar WSDL. Don't cache on self so subsequent calls
            # on this client stay pointed at the original PS service.
            try:
                transport = Transport(
                    cache=_WSDL_CACHE, timeout=60, operation_timeout=300
                )
                svc = ZeepClient(extension_wsdl_url, transport=transport).service
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "extension WSDL %s unreachable: %s", extension_wsdl_url, exc
                )
                return []
            return self._sanmar_products_by_category(svc, category_name, limit)

        # Standard PS path (assumes non-SanMar supplier exposes the op on their
        # ProductData binding; most PS suppliers do NOT implement this).
        svc = self._get_service()
        try:
            response = svc.getProductInfoByCategory(
                category=category_name,
                **self._auth(ws_version, localization_country, localization_language),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("getProductInfoByCategory(%s) failed: %s", category_name, exc)
            return []

        products_container = _attr(
            response, "ProductArray", "productArray", "Products", "products"
        )
        product_items = _as_list(_attr(products_container, "Product", "product"))

        out: list[PSProductData] = []
        for item in product_items:
            if limit and len(out) >= limit:
                break
            parsed = self._parse_product(item)
            if parsed is not None:
                out.append(parsed)
        return out

    # ------------------------------------------------------------------
    # SanMar-specific category fetch (non-PS extension)
    # ------------------------------------------------------------------

    def _sanmar_auth_payload(self) -> dict:
        """Build the ``webServiceUser`` complex type SanMar's ext expects.

        auth_config layout we accept (decrypted):
          - customer_number / sanMarCustomerNumber
          - id OR username OR sanMarUserName
          - password OR sanMarUserPassword
          - sender_id / senderId (optional, default 0)
          - sender_password / senderPassword (optional, default "")
        """
        ac = self.auth_config or {}
        return {
            "sanMarCustomerNumber": str(
                ac.get("customer_number")
                or ac.get("sanMarCustomerNumber")
                or ac.get("id")
                or ""
            ),
            "sanMarUserName": str(
                ac.get("username")
                or ac.get("sanMarUserName")
                or ac.get("id")
                or ""
            ),
            "sanMarUserPassword": str(
                ac.get("password") or ac.get("sanMarUserPassword") or ""
            ),
            "senderId": int(
                ac.get("sender_id") or ac.get("senderId") or 0
            ),
            "senderPassword": str(
                ac.get("sender_password") or ac.get("senderPassword") or ""
            ),
        }

    def _sanmar_products_by_category(
        self, svc: Any, category_name: str, limit: int
    ) -> list[PSProductData]:
        # WSDL requires arg0=productCategory, arg1=webServiceUser. SanMar
        # accepts the webServiceUser with just 3 creds (id, password,
        # customer_number); senderId defaults to 0 and senderPassword to ""
        # and SanMar tolerates that for most category calls.
        try:
            response = svc.getProductInfoByCategory(
                arg0={"category": category_name},
                arg1=self._sanmar_auth_payload(),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "SanMar getProductInfoByCategory(%s) failed: %s",
                category_name,
                exc,
            )
            return []

        if _text(_attr(response, "errorOccured")) in ("true", "True", "1"):
            msg = _text(_attr(response, "message")) or "unknown"
            log.warning("SanMar getProductInfoByCategory error: %s", msg)
            return []

        items = _as_list(_attr(response, "listResponse"))
        log.info(
            "SanMar getProductInfoByCategory(%s): %d rows received",
            category_name,
            len(items),
        )
        # Group rows by style — SanMar returns one row per color/size combo.
        # Cap parts-per-style so a single category doesn't balloon into
        # thousands of variants per product. 200 covers typical SanMar styles
        # (12 colors × 10 sizes = 120) with headroom.
        MAX_PARTS_PER_STYLE = 200
        grouped: dict[str, PSProductData] = {}
        for item in items:
            # Fast-exit: once we have `limit` styles and all are saturated,
            # further iteration just wastes parse time.
            if (
                limit
                and len(grouped) >= limit
                and all(len(p.parts) >= MAX_PARTS_PER_STYLE for p in grouped.values())
            ):
                break

            basic = _attr(item, "productBasicInfo")
            img = _attr(item, "productImageInfo")
            price = _attr(item, "productPriceInfo")
            style = _text(_attr(basic, "style"))
            if not style:
                continue

            # Skip discontinued SKUs — SanMar returns them in the catalog but
            # they're not orderable. Both productStatus == "Discontinued" and
            # a "DISCONTINUED" prefix on productTitle appear in the wild.
            status = _text(_attr(basic, "productStatus")).lower()
            title_raw = _text(_attr(basic, "productTitle"))
            if "discontinu" in status or title_raw.upper().startswith("DISCONTINUED"):
                continue

            if style not in grouped:
                if limit and len(grouped) >= limit:
                    continue
                # SanMar's response usually omits 'category' on each product
                # even when we filtered by category. Fall back to the
                # category_name argument we asked SanMar for — every product
                # in this response is, by definition, in that category.
                cat_name = _text(_attr(basic, "category")) or category_name
                grouped[style] = PSProductData(
                    product_id=style,
                    product_name=_text(_attr(basic, "productTitle")),
                    description=_text(_attr(basic, "productDescription")),
                    brand=_text(_attr(basic, "brandName")),
                    categories=[cat_name] if cat_name else [],
                    product_type="apparel",
                    primary_image_url=_text(
                        _attr(img, "productImage", "frontModel", "colorProductImage")
                    ),
                    parts=[],
                )

            prod = grouped.get(style)
            if prod is None:
                continue

            if len(prod.parts) >= MAX_PARTS_PER_STYLE:
                continue

            part_id = _text(_attr(basic, "uniqueKey")) or _text(
                _attr(basic, "inventoryKey")
            )
            if part_id:
                prod.parts.append(
                    PSProductPart(
                        part_id=part_id,
                        color_name=(
                            _text(_attr(basic, "color"))
                            or _text(_attr(basic, "catalogColor"))
                        ),
                        size_name=_text(_attr(basic, "size")),
                        description=None,
                        attributes={
                            k: v
                            for k, v in {
                                "piece_price": _text(_attr(price, "piecePrice")),
                                "dozen_price": _text(_attr(price, "dozenPrice")),
                                "case_price": _text(_attr(price, "casePrice")),
                                "color_image": _text(_attr(img, "colorProductImage")),
                            }.items()
                            if v
                        },
                    )
                )

        out = list(grouped.values())[: limit or None]
        log.info(
            "SanMar getProductInfoByCategory(%s): %d unique styles (limit=%d)",
            category_name,
            len(out),
            limit,
        )
        return out

    # -- Inventory ---------------------------------------------------------

    async def get_inventory(
        self,
        product_ids: list[str],
        ws_version: str = "2.0.0",
        part_ids: list[str] | None = None,
    ) -> list[PSInventoryLevel]:
        """Fetch inventory for ``product_ids``.

        When ``part_ids`` is provided we call ``getFilteredInventoryLevels``
        (PromoStandards Inventory 2.0.0) — SanMar's v200 endpoint returns empty
        or times out on the unfiltered ``getInventoryLevels`` for catalogs
        with many SKUs, but always responds correctly to the filtered variant.

        Without ``part_ids`` we fall back to ``getInventoryLevels`` for
        suppliers whose implementation supports the simpler call.
        """
        return await asyncio.to_thread(
            self._sync_get_inventory, product_ids, ws_version, part_ids
        )

    def _sync_get_inventory(
        self,
        product_ids: list[str],
        ws_version: str,
        part_ids: list[str] | None = None,
    ) -> list[PSInventoryLevel]:
        svc = self._get_service()
        out: list[PSInventoryLevel] = []
        for pid in product_ids:
            response = self._call_inventory(svc, pid, ws_version, part_ids)
            if response is None:
                continue
            out.extend(self._parse_inventory(response, pid))
        return out

    def _call_inventory(
        self,
        svc: Any,
        product_id: str,
        ws_version: str,
        part_ids: list[str] | None,
    ) -> Any:
        """Try filtered first when part_ids are known; fall back to unfiltered.

        SanMar v200 reliably answers ``getFilteredInventoryLevels`` and often
        rejects/empties ``getInventoryLevels`` for full-catalog queries; other
        PromoStandards implementations (S&S, Alphabroder) are the opposite.
        Calling filtered-first when we have part IDs covers both worlds.
        """
        if part_ids:
            try:
                return svc.getFilteredInventoryLevels(
                    productId=product_id,
                    partIdArray={"partId": part_ids},
                    **self._auth(ws_version),
                )
            except Exception as exc:  # noqa: BLE001
                log.warning(
                    "getFilteredInventoryLevels(%s) failed, falling back: %s",
                    product_id,
                    exc,
                )
        try:
            return svc.getInventoryLevels(
                productId=product_id, **self._auth(ws_version)
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("getInventoryLevels(%s) failed: %s", product_id, exc)
            return None

    def _parse_inventory(self, response: Any, product_id: str) -> Iterable[PSInventoryLevel]:
        inv_root = _attr(response, "Inventory", "inventory") or response
        for inv_record in _as_list(inv_root):
            rec_pid = _text(_attr(inv_record, "productId")) or product_id
            parts_container = _attr(
                inv_record,
                "PartInventoryArray",
                "partInventoryArray",
                "ProductVariationInventoryArray",
            )
            part_items = _as_list(
                _attr(
                    parts_container,
                    "PartInventory",
                    "partInventory",
                    "ProductVariationInventory",
                )
            )
            for part in part_items:
                part_id = _text(_attr(part, "partId", "part_id"))
                if not part_id:
                    continue
                qty, warehouse = self._extract_inventory_qty_and_warehouse(part)
                yield PSInventoryLevel(
                    product_id=rec_pid,
                    part_id=part_id,
                    quantity_available=qty,
                    warehouse_code=warehouse,
                )

    def _extract_inventory_qty_and_warehouse(self, part: Any) -> tuple[int, str | None]:
        """Return (total_quantity, primary_warehouse_name) for one part.

        SanMar nests qty as ``<quantityAvailable><Quantity><value>N</value></Quantity></quantityAvailable>``
        and repeats ``<InventoryLocation>`` with its own ``<inventoryLocationQuantity>``.
        Aggregate across locations when per-location quantities are present;
        otherwise fall back to the top-level ``quantityAvailable``. Primary
        warehouse is the highest-stock location.
        """
        loc_container = _attr(part, "InventoryLocationArray", "inventoryLocationArray")
        locs = _as_list(_attr(loc_container, "InventoryLocation", "inventoryLocation"))

        best_qty = -1
        best_name: str | None = None
        sum_qty = 0
        any_location_qty = False
        for loc in locs:
            loc_qty_wrapper = _attr(loc, "inventoryLocationQuantity")
            quantity_obj = _attr(loc_qty_wrapper, "Quantity", "quantity") if loc_qty_wrapper else None
            loc_qty_raw = _attr(quantity_obj, "value") if quantity_obj else None
            if loc_qty_raw is None:
                continue
            any_location_qty = True
            loc_qty = self._coerce_int(loc_qty_raw)
            sum_qty += loc_qty
            if loc_qty > best_qty:
                best_qty = loc_qty
                best_name = _text(
                    _attr(loc, "inventoryLocationName", "inventoryLocationId", "name")
                )

        if any_location_qty:
            return sum_qty, best_name

        # No per-location quantities — use top-level quantityAvailable.
        qty_container = _attr(part, "quantityAvailable", "quantity")
        nested_q = _attr(qty_container, "Quantity") if qty_container is not None else None
        if nested_q is not None:
            qty = self._coerce_int(_attr(nested_q, "value"))
        else:
            qty = self._coerce_int(qty_container)

        warehouse_name: str | None = None
        if locs:
            warehouse_name = _text(
                _attr(locs[0], "inventoryLocationName", "inventoryLocationId", "name")
            )
        return qty, warehouse_name

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
        self,
        product_ids: list[str],
        ws_version: str = "1.0.0",
        fob_id: str = "1",
        price_type: str = "Net",
        currency: str = "USD",
        configuration_type: str = "Blank",
        localization_country: str = "US",
        localization_language: str = "EN",
    ) -> list[PSPricePoint]:
        return await asyncio.to_thread(
            self._sync_get_pricing,
            product_ids,
            ws_version,
            fob_id,
            price_type,
            currency,
            configuration_type,
            localization_country,
            localization_language,
        )

    def _sync_get_pricing(
        self,
        product_ids: list[str],
        ws_version: str,
        fob_id: str,
        price_type: str,
        currency: str,
        configuration_type: str,
        localization_country: str,
        localization_language: str,
    ) -> list[PSPricePoint]:
        svc = self._get_service()
        out: list[PSPricePoint] = []
        for pid in product_ids:
            try:
                response = svc.getConfigurationAndPricing(
                    productId=pid,
                    currency=currency,
                    fobId=fob_id,
                    priceType=price_type,
                    configurationType=configuration_type,
                    **self._auth(ws_version, localization_country, localization_language)
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
        self, product_ids: list[str], ws_version: str = "1.1.0", media_type: str = "Image"
    ) -> list[PSMediaItem]:
        semaphore = asyncio.Semaphore(5)  # Max 5 concurrent SOAP calls

        async def _fetch_single_media(pid: str) -> list[PSMediaItem]:
            async with semaphore:
                try:
                    return await asyncio.to_thread(self._sync_get_single_media, pid, ws_version, media_type)
                except Exception as exc:
                    log.warning("getMediaContent(%s) failed: %s", pid, exc)
                    return []

        tasks = [_fetch_single_media(pid) for pid in product_ids]
        results = await asyncio.gather(*tasks)
        
        out: list[PSMediaItem] = []
        for r in results:
            out.extend(r)
        return out

    def _sync_get_single_media(
        self, product_id: str, ws_version: str, media_type: str
    ) -> list[PSMediaItem]:
        svc = self._get_service()
        response = svc.getMediaContent(
            productId=product_id,
            mediaType=media_type,
            **self._auth(ws_version)
        )
        return list(self._parse_media(response, product_id))

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
