"""Generic PromoStandards adapter.

Wraps modules.promostandards.client.PromoStandardsClient (zeep-based) and
modules.promostandards.ps_normalizer_v2 (pure XML -> ProductIngest). Resolves
WSDL URLs via supplier.endpoint_cache (PS Directory).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional, List, Any

from lxml import etree
from modules.catalog.schemas import ProductIngest

from modules.import_jobs.base import (
    AuthError,
    BaseAdapter,
    DiscoveryMode,
    ProductRef,
    SupplierError,
    TransientError,
)

# Security: Disable entity resolution to prevent XXE attacks
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)

from modules.import_jobs.registry import register_adapter
from modules.suppliers.models import Supplier
from sqlalchemy.ext.asyncio import AsyncSession

from .resolver import resolve_wsdl_url

log = logging.getLogger(__name__)

_AUTH_CODES = {"100", "104", "110"}


def _classify_fault_xml(xml_bytes: bytes) -> None:
    """Translate a SOAP Fault envelope into AuthError or SupplierError.

    Returns silently if the envelope is not a Fault (caller continues).
    """
    root = etree.fromstring(xml_bytes, _PARSER)
    fault = root.xpath("//*[local-name()='Fault']")
    if not fault:
        return
    # Use lowercase comparison for robustness
    code_node = root.xpath(
        "//*[translate(local-name(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='errormessage']"
        "/*[translate(local-name(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='code']"
    )
    msg_node = root.xpath(
        "//*[translate(local-name(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='errormessage']"
        "/*[translate(local-name(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='description' or "
        "translate(local-name(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz')='message']"
    )
    code = (code_node[0].text or "").strip() if code_node else ""
    message = (msg_node[0].text or "").strip() if msg_node else "Unknown PS fault"
    if code in _AUTH_CODES:
        raise AuthError(f"[{code}] {message}")
    raise SupplierError(message, code or "999")





class PromoStandardsAdapter(BaseAdapter):
    product_type = "apparel"

    def __init__(self, supplier, db):
        super().__init__(supplier=supplier, db=db)
        self._client_cache: dict[str, Any] = {}

    def _require_auth(self) -> dict:
        auth = dict(self.supplier.auth_config or {})
        ps_id = auth.get("id")
        password = auth.get("password")
        if not ps_id or not password:
            raise AuthError(
                f"Supplier {self.supplier.name!r} missing PromoStandards id/password"
            )
        return {"id": ps_id, "password": password}

    def _wsdl_for(self, service_type: str) -> str:
        # Try dynamic cache (PS Directory)
        cached = super()._wsdl_for(service_type)
        if cached:
            return cached
            
        raise SupplierError(f"WSDL for service {service_type!r} not in endpoint_cache", "wsdl_missing")

    async def discover(
        self, mode: DiscoveryMode, limit: Optional[int] = None, explicit_list: Optional[List[str]] = None
    ) -> list[ProductRef]:
        self._require_auth()
        cfg = dict(self.supplier.protocol_config or {})
        
        if mode is DiscoveryMode.EXPLICIT_LIST:
            ids = explicit_list or cfg.get("explicit_list") or []
            if limit is not None:
                ids = ids[:limit]
            return [ProductRef(supplier_sku=str(i)) for i in ids]
            
        # FIRST_N / FILTERED_SAMPLE / FULL_SELLABLE all hit GetProductSellable.
        if mode in (
            DiscoveryMode.FIRST_N,
            DiscoveryMode.FILTERED_SAMPLE,
            DiscoveryMode.FULL_SELLABLE,
        ):
            refs = await self._call_get_product_sellable()
            if mode is DiscoveryMode.FILTERED_SAMPLE:
                wanted = explicit_list or cfg.get("explicit_list") or []
                wanted_set = set(map(str, wanted))
                refs = [r for r in refs if r.supplier_sku in wanted_set]
            if limit is not None:
                refs = refs[:limit]
            return refs
            
        if mode is DiscoveryMode.DELTA:
            since = self.get_delta_since_timestamp()
            return await self.discover_changed(since)
            
        if mode is DiscoveryMode.CLOSEOUTS:
            return await self.discover_closeouts()
            
        raise NotImplementedError(f"discovery mode {mode!r} not supported")

    async def hydrate_product(self, ref: ProductRef) -> ProductIngest:
        self._require_auth()
        get_product_xml = await self._call_get_product(ref)
        
        from .ps_normalizer_v2 import (
            merge_media,
            merge_pricing,
            normalize_get_product_xml,
        )

        ingest = normalize_get_product_xml(get_product_xml)
        
        try:
            pricing_xml = await self._call_get_pricing(ref)
            ingest = merge_pricing(ingest, pricing_xml)
        except Exception as exc:
            log.warning("Pricing fetch failed for %s: %s", ref.supplier_sku, exc)
            
        try:
            media_xml = await self._call_get_media(ref)
            ingest = merge_media(ingest, media_xml)
        except Exception as exc:
            log.warning("Media fetch failed for %s: %s", ref.supplier_sku, exc)

        # Bug 4 fix: Inventory v200 — pass the variant part_ids so SanMar v200
        # uses getFilteredInventoryLevels (which it actually answers) instead
        # of the bare getInventoryLevels (which returns empty / times out on
        # SanMar's implementation). client.get_inventory() returns parsed
        # PSInventoryLevel rows; map them back onto each variant by part_id.
        # INVENTORY WSDL must exist in the supplier's endpoint cache; if not,
        # swallow and continue (existing downstream code already treats
        # variant.inventory=None as "unknown").
        try:
            inv_client = self._get_client("INVENTORY")
            part_ids = [v.part_id for v in ingest.variants if v.part_id]
            inv_levels = await inv_client.get_inventory(
                [ref.supplier_sku], part_ids=part_ids or None
            )
            inv_by_part = {level.part_id: level for level in inv_levels}
            for variant in ingest.variants:
                level = inv_by_part.get(variant.part_id)
                if level is None:
                    continue
                variant.inventory = level.quantity_available
                if level.warehouse_code and not variant.warehouse:
                    variant.warehouse = level.warehouse_code
        except Exception as exc:
            log.warning("Inventory fetch failed for %s: %s", ref.supplier_sku, exc)

        return ingest

    async def hydrate_inventory_only(self, ref: ProductRef) -> dict[str, int]:
        """Fetch only inventory levels — skips product/pricing/media SOAP calls.

        Queries the local DB for existing variant part_ids so we can use
        getFilteredInventoryLevels (SanMar v200 requires filtered call).
        Returns {part_id: quantity_available}.
        """
        self._require_auth()
        try:
            from sqlalchemy import select as sa_select
            from modules.catalog.models import Product, ProductVariant
            part_ids = (await self.db.execute(
                sa_select(ProductVariant.part_id)
                .join(Product, Product.id == ProductVariant.product_id)
                .where(
                    Product.supplier_sku == ref.supplier_sku,
                    Product.supplier_id == self.supplier.id,
                    ProductVariant.part_id.isnot(None),
                )
            )).scalars().all()
            if not part_ids:
                return {}
            inv_client = self._get_client("INVENTORY")
            inv_levels = await inv_client.get_inventory(
                [ref.supplier_sku], part_ids=list(part_ids)
            )
            return {
                level.part_id: level.quantity_available
                for level in inv_levels
                if level.part_id is not None
            }
        except Exception as exc:
            log.warning("Inventory-only fetch failed for %s: %s", ref.supplier_sku, exc)
            return {}

    async def discover_changed(self, since: datetime) -> list[ProductRef]:
        self._require_auth()
        return await self._call_get_product_date_modified(since)

    async def discover_closeouts(self) -> list[ProductRef]:
        self._require_auth()
        return await self._call_get_product_closeout()

    # ----- Transport hooks (production using zeep/client) -----

    def _get_client(self, service_type: str) -> Any:
        if service_type not in self._client_cache:
            from .client import PromoStandardsClient
            wsdl = self._wsdl_for(service_type)
            self._client_cache[service_type] = PromoStandardsClient(
                wsdl_url=wsdl, auth_config=self.supplier.auth_config
            )
        return self._client_cache[service_type]

    async def _call_get_product_sellable(self) -> list[ProductRef]:
        client = self._get_client("PRODUCT")
        pids = await client.get_sellable_product_ids()
        return [ProductRef(supplier_sku=pid) for pid in pids]

    async def _call_get_product(self, ref: ProductRef) -> bytes:
        client = self._get_client("PRODUCT")
        import asyncio
        from zeep.exceptions import TransportError
        
        def _sync_call():
            svc, h = client.get_service_with_history()
            try:
                svc.getProduct(
                    productId=ref.supplier_sku,
                    **client._auth(ws_version="2.0.0", localization_country="us", localization_language="en")
                )
            except TransportError as te:
                raise TransientError(f"Network timeout: {te}") from te
            except Exception:
                if h.last_received and h.last_received.get("envelope") is not None:
                    _classify_fault_xml(etree.tostring(h.last_received["envelope"]))
                raise
            body = etree.tostring(h.last_received["envelope"])
            _classify_fault_xml(body)
            return body

        return await asyncio.to_thread(_sync_call)

    async def _call_get_pricing(self, ref: ProductRef) -> bytes:
        client = self._get_client("PRICING")
        import asyncio
        from zeep.exceptions import TransportError
        def _sync_call():
            svc, h = client.get_service_with_history()
            try:
                svc.getConfigurationAndPricing(
                    productId=ref.supplier_sku,
                    currency="USD",
                    fobId="1",
                    priceType="Net",
                    configurationType="Blank",
                    **client._auth(
                        ws_version="1.0.0",
                        localization_country="us",
                        localization_language="en",
                    ),
                )
            except TransportError as te:
                raise TransientError(f"Network timeout: {te}") from te
            except Exception:
                # zeep's HistoryPlugin raises IndexError when buffer is empty
                # (e.g. WSDL-validation errors that fail before the network
                # send). Guard with try/except so we surface the real error
                # instead of a confusing "deque index out of range".
                try:
                    last = h.last_received
                except IndexError:
                    last = None
                if last and last.get("envelope") is not None:
                    _classify_fault_xml(etree.tostring(last["envelope"]))
                raise
            try:
                last = h.last_received
            except IndexError:
                last = None
            if last is None or last.get("envelope") is None:
                raise TransientError(
                    f"getConfigurationAndPricing returned no envelope for {ref.supplier_sku}"
                )
            body = etree.tostring(last["envelope"])
            _classify_fault_xml(body)
            return body
        return await asyncio.to_thread(_sync_call)

    async def _call_get_media(self, ref: ProductRef) -> bytes:
        client = self._get_client("MEDIA")
        import asyncio
        from zeep.exceptions import TransportError
        def _sync_call():
            svc, h = client.get_service_with_history()
            try:
                svc.getMediaContent(
                    productId=ref.supplier_sku,
                    mediaType="Image",
                    **client._auth(ws_version="1.1.0")
                )
            except TransportError as te:
                raise TransientError(f"Network timeout: {te}") from te
            except Exception:
                if h.last_received and h.last_received.get("envelope") is not None:
                    _classify_fault_xml(etree.tostring(h.last_received["envelope"]))
                raise
            body = etree.tostring(h.last_received["envelope"])
            _classify_fault_xml(body)
            return body
        return await asyncio.to_thread(_sync_call)

    async def _call_get_product_date_modified(self, since: datetime) -> list[ProductRef]:
        client = self._get_client("PRODUCT")
        import asyncio
        def _sync():
            svc = client._get_service()
            res = svc.getProductDateModified(
                changeTimeStamp=since.isoformat(),
                **client._auth(ws_version="2.0.0")
            )
            out: list[ProductRef] = []
            # res is usually a list of objects with productId, partId
            for item in (res or []):
                pid = getattr(item, "productId", None)
                qid = getattr(item, "partId", None)
                if pid:
                    out.append(ProductRef(supplier_sku=str(pid), part_id=str(qid) if qid else None))
            return out
        return await asyncio.to_thread(_sync)

    async def _call_get_product_closeout(self) -> list[ProductRef]:
        client = self._get_client("PRODUCT")
        import asyncio
        def _sync():
            svc = client._get_service()
            res = svc.getProductCloseOut(
                **client._auth(ws_version="2.0.0")
            )
            out: list[ProductRef] = []
            for item in (res or []):
                pid = getattr(item, "productId", None)
                qid = getattr(item, "partId", None)
                if pid:
                    out.append(ProductRef(supplier_sku=str(pid), part_id=str(qid) if qid else None))
            return out
        return await asyncio.to_thread(_sync)




# Self-register
register_adapter("PromoStandardsAdapter", PromoStandardsAdapter)
