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
)
from modules.import_jobs.registry import register_adapter
from modules.suppliers.models import Supplier
from sqlalchemy.ext.asyncio import AsyncSession

from .resolver import resolve_wsdl_url

log = logging.getLogger(__name__)

_AUTH_CODES = {"100", "104", "110"}
_PARSER = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=False)


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
        cache = self.supplier.endpoint_cache or []
        url = resolve_wsdl_url(cache, service_type)
        if not url:
            raise SupplierError(
                f"WSDL for service {service_type!r} not in endpoint_cache for supplier {self.supplier.name!r}",
                "wsdl_missing",
            )
        return url

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
            
        return ingest

    async def discover_changed(self, since: datetime) -> list[ProductRef]:
        self._require_auth()
        return await self._call_get_product_date_modified(since)

    async def discover_closeouts(self) -> list[ProductRef]:
        self._require_auth()
        return await self._call_get_product_closeout()

    # ----- Transport hooks (production using zeep/client) -----

    def _get_client(self, service_type: str) -> Any:
        from .client import PromoStandardsClient
        wsdl = self._wsdl_for(service_type)
        return PromoStandardsClient(wsdl_url=wsdl, auth_config=self.supplier.auth_config)

    async def _call_get_product_sellable(self) -> list[ProductRef]:
        client = self._get_client("PRODUCT")
        pids = await client.get_sellable_product_ids()
        return [ProductRef(supplier_sku=pid) for pid in pids]

    async def _call_get_product(self, ref: ProductRef) -> bytes:
        client = self._get_client("PRODUCT")
        from zeep.plugins import HistoryPlugin
        import asyncio
        
        def _sync_call():
            from zeep import Client as ZeepClient
            from zeep.transports import Transport
            h = HistoryPlugin()
            c = ZeepClient(client.wsdl_url, transport=Transport(), plugins=[h])
            try:
                c.service.getProduct(
                    productId=ref.supplier_sku,
                    **client._auth(ws_version="2.0.0", localization_country="us", localization_language="en")
                )
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
        from zeep.plugins import HistoryPlugin
        import asyncio
        def _sync_call():
            from zeep import Client as ZeepClient
            from zeep.transports import Transport
            h = HistoryPlugin()
            c = ZeepClient(client.wsdl_url, transport=Transport(), plugins=[h])
            try:
                c.service.getConfigurationAndPricing(
                    productId=ref.supplier_sku,
                    currency="USD",
                    fobId="1",
                    priceType="Net",
                    configurationType="Blank",
                    **client._auth(ws_version="1.0.0")
                )
            except Exception:
                if h.last_received and h.last_received.get("envelope") is not None:
                    _classify_fault_xml(etree.tostring(h.last_received["envelope"]))
                raise
            body = etree.tostring(h.last_received["envelope"])
            _classify_fault_xml(body)
            return body
        return await asyncio.to_thread(_sync_call)

    async def _call_get_media(self, ref: ProductRef) -> bytes:
        client = self._get_client("MEDIA")
        from zeep.plugins import HistoryPlugin
        import asyncio
        def _sync_call():
            from zeep import Client as ZeepClient
            from zeep.transports import Transport
            h = HistoryPlugin()
            c = ZeepClient(client.wsdl_url, transport=Transport(), plugins=[h])
            try:
                c.service.getMediaContent(
                    productId=ref.supplier_sku,
                    mediaType="Image",
                    **client._auth(ws_version="1.1.0")
                )
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
