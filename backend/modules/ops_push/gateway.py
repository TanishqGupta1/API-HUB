"""Integration Gateway core — prepare_push_intent() + execute_push()."""
from __future__ import annotations

import asyncio
import logging
import re
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import async_session
from modules.catalog.models import Product, CustomerProductSelection
from modules.customers.models import Customer
from modules.integrations.models import IntegrationKey
from modules.integrations.schemas import PushRequest, PushRequestAccepted, PushRequestLinks
from modules.markup.engine import calculate_price
from modules.ops_client import mutations as _m
from modules.ops_client.client import OpsAuth, OpsGraphQLClient, OpsResult
from modules.ops_push.payload_builder import build_push_payload, compute_payload_hash
from modules.ops_push.preflight import run_preflight
from modules.push_log.models import ProductPushLog
from modules.push_mappings.models import PushMapping
from modules.suppliers.models import Supplier
from modules.webhooks.service import fire_webhooks

logger = logging.getLogger(__name__)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# OPS clients — adapters that match the plan-step interface
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#
# `execute_push` walks the OPSMutationStep plan from payload_builder, calling
# `getattr(client, _mutation_to_method(step.mutation))(step.variables)` for
# each step. The OPS client adapter and the dry-run Fake share that
# (variables: dict) → response: dict interface.

# Maps GraphQL mutation root → (query string, response root key).
# The query strings live in ops_client.mutations as the single source of
# truth for OPS field shapes.
async def _dedup_lookup_in_ops(
    client: Any, supplier_sku: str
) -> Optional[int]:
    """Ask OPS whether it already has a product with this SKU.

    Defensive: any error (auth, schema mismatch, transport) is logged and
    returns None so the push falls through to its normal create-or-update
    path. We never want a flaky dedup query to BLOCK a legitimate push.

    Returns the OPS products_id when a match exists, else None.
    """
    try:
        result = await _m.get_product_by_sku(client=client, products_sku=supplier_sku)
    except Exception:  # noqa: BLE001 — defensive
        logger.exception("dedup: get_product_by_sku raised for sku=%s", supplier_sku)
        return None
    if not result.ok:
        logger.warning(
            "dedup: get_product_by_sku not OK for sku=%s: %s",
            supplier_sku, result.ops_error_message,
        )
        return None
    pid = (result.data or {}).get("products_id")
    if pid is None:
        return None
    try:
        return int(pid)
    except (TypeError, ValueError):
        logger.warning("dedup: OPS returned non-numeric products_id=%r for sku=%s", pid, supplier_sku)
        return None


async def _verify_post_push(
    client: Any, supplier_sku: str, expected_ops_product_id: str
) -> None:
    """Read-back the just-pushed product and verify OPS sees it with the
    expected products_id. Logs a warning on mismatch; never raises and
    never blocks the push. Opt-in via OPS_POST_PUSH_VERIFY=1.

    Cheap sanity layer for the first weeks of live pushes — if OPS
    silently dropped a write or our id-threading drifted, this surfaces
    the bug before customers notice."""
    import os as _os
    if _os.getenv("OPS_POST_PUSH_VERIFY", "0") != "1":
        return
    try:
        result = await _m.get_product_by_sku(client=client, products_sku=supplier_sku)
    except Exception:  # noqa: BLE001
        logger.exception("verify: get_product_by_sku raised for sku=%s", supplier_sku)
        return
    if not result.ok:
        logger.warning(
            "verify: get_product_by_sku not OK after push sku=%s: %s",
            supplier_sku, result.ops_error_message,
        )
        return
    observed = (result.data or {}).get("products_id")
    if observed is None:
        logger.warning(
            "verify: OPS returned no products_id for sku=%s after push (expected=%s)",
            supplier_sku, expected_ops_product_id,
        )
        return
    if str(observed) != str(expected_ops_product_id):
        logger.warning(
            "verify: OPS products_id mismatch sku=%s expected=%s observed=%s — investigate",
            supplier_sku, expected_ops_product_id, observed,
        )
    else:
        logger.info(
            "verify: OPS confirmed sku=%s -> products_id=%s",
            supplier_sku, observed,
        )


# Per-product cache of (size_id -> stock_id) maps. Populated lazily on the
# first updateProductStock call of a product so we only query OPS once per
# product per push (not once per variant).
_stock_lookup_cache: dict[int, dict[int, int]] = {}


async def _resolve_stock_id_for_size(
    client: Any, *, product_id: Optional[int], size_id: int
) -> Optional[int]:
    """Find the OPS stock_id for a given (product_id, size_id) pair.

    Phase 6: OPS's updateProductStock requires a stock_id but provides no
    API to create initial stock entries — those must be initialized via
    the OPS admin UI. This helper queries OPS once per product for its
    existing stock entries, caches the size_id -> stock_id map, and
    returns the matching stock_id (or None when no entry exists yet).

    Defensive: returns None on any error so the caller records an
    actionable warning instead of aborting the push.

    Dry-run / FakeOpsClient: the dry-run client has no `execute` method
    (it implements per-mutation methods directly). Return a synthetic
    stock_id so dry-runs exercise the full plan and don't generate
    spurious "no stock entry" warnings.
    """
    if product_id is None:
        return None
    # Dry-run path: FakeOpsClient has no execute(); return a fake id so
    # the stock step runs through (it's a fake call anyway).
    if not hasattr(client, "execute"):
        return 99000 + int(size_id)  # stable fake id, distinct per variant
    cache_key = product_id
    if cache_key not in _stock_lookup_cache:
        try:
            r = await _m.get_product_stocks(client=client, product_id=product_id)
        except Exception:  # noqa: BLE001
            logger.exception("stock-lookup: get_product_stocks raised for product_id=%s", product_id)
            return None
        if not r.ok:
            logger.warning(
                "stock-lookup: get_product_stocks not OK for product_id=%s: %s",
                product_id, r.ops_error_message,
            )
            return None
        entries = (r.data or {}).get("productStocks") or []
        _stock_lookup_cache[cache_key] = {
            int(e["size_id"]): int(e["stock_id"])
            for e in entries
            if e.get("size_id") is not None and e.get("stock_id") is not None
        }
    return _stock_lookup_cache[cache_key].get(int(size_id))


def _clear_stock_lookup_cache(product_id: int) -> None:
    """Forget the cached stock map for a product. Call after the push so a
    later push for the same product sees freshly-initialized entries."""
    _stock_lookup_cache.pop(product_id, None)


async def _ensure_push_mapping_for_dedup(
    db: AsyncSession,
    customer: Customer,
    product_id: uuid_mod.UUID,
    supplier_sku: str,
    ops_product_id: int,
) -> None:
    """Upsert push_mappings.target_ops_product_id so build_push_payload
    sees it and chooses update mode. Called only when dedup discovered
    an existing OPS row we didn't know about (e.g. after a crash
    between OPS write and mapping save in a prior push)."""
    now = datetime.now(timezone.utc)
    existing = (await db.execute(
        select(PushMapping).where(
            PushMapping.source_product_id == product_id,
            PushMapping.customer_id == customer.id,
        )
    )).scalar_one_or_none()
    if existing:
        existing.target_ops_product_id = ops_product_id
        existing.updated_at = now
        return
    db.add(PushMapping(
        source_system="api-hub",
        source_product_id=product_id,
        source_supplier_sku=supplier_sku,
        customer_id=customer.id,
        target_ops_base_url=customer.ops_base_url or "",
        target_ops_product_id=ops_product_id,
        pushed_at=now,
        updated_at=now,
        status="active",
    ))


_MUTATION_DISPATCH: dict[str, tuple[str, str]] = {
    "set_product_category":            (_m._SET_PRODUCT_CATEGORY,            "setProductCategory"),
    "set_product":                     (_m._SET_PRODUCT,                     "setProduct"),
    "set_product_size":                (_m._SET_PRODUCT_SIZE,                "setProductSize"),
    "set_product_price":               (_m._SET_PRODUCT_PRICE,               "setProductPrice"),
    "set_assign_options":              (_m._SET_ASSIGN_OPTIONS,              "setAssignOptions"),
    "set_additional_option":           (_m._SET_ADDITIONAL_OPTION,           "setAdditionalOption"),
    "set_additional_option_attributes": (_m._SET_ADDITIONAL_OPTION_ATTRIBUTES, "setAdditionalOptionAttributes"),
    "set_products_attribute_price":    (_m._SET_PRODUCTS_ATTRIBUTE_PRICE,    "setProductsAttributePrice"),
    "set_products_image_gallery":      (_m._SET_PRODUCTS_IMAGE_GALLERY,      "setProductsImageGallery"),
    "update_product_stock":            (_m._UPDATE_PRODUCT_STOCK,            "updateProductStock"),
}


class OpsClientAdapter:
    """Live OPS client — dispatches each plan step through OpsGraphQLClient."""

    def __init__(self, client: OpsGraphQLClient) -> None:
        self._client = client

    async def aclose(self) -> None:
        await self._client.aclose()

    async def execute(self, query: str, *, variables: dict) -> OpsResult:
        """Raw GraphQL passthrough for read queries (dedup / post-push verify
        call ``get_product_by_sku``, which calls ``client.execute``).

        ``__getattr__`` only resolves the mutation method names, so without an
        explicit ``execute`` here every dedup/verify lookup raised
        ``AttributeError: execute`` and was silently swallowed — dedup never ran
        on a live push. Defined as a real method so normal lookup finds it
        before ``__getattr__``.
        """
        return await self._client.execute(query, variables=variables)

    def __getattr__(self, name: str) -> Any:
        if name not in _MUTATION_DISPATCH:
            raise AttributeError(name)
        query, response_root = _MUTATION_DISPATCH[name]

        async def _invoke(variables: dict) -> dict:
            result = await self._client.execute(query, variables=variables)
            if not result.ok:
                code = result.ops_error_code or "OPS_ERROR"
                msg = result.ops_error_message or "OPS mutation failed"
                raise RuntimeError(f"{code}: {msg}")
            data = (result.data or {}).get(response_root)
            if isinstance(data, list):
                data = data[0] if data else {}
            data = data or {}
            # ── Application-level silent-failure detection ────────────
            # OPS returns HTTP 200 + result:false when a mutation is
            # rejected at the app layer (missing required field, etc.).
            # The wrapper functions in mutations.py have _check_result,
            # but THIS path bypasses those wrappers and talks directly
            # to OPS. Without this check the gateway records steps as
            # `ok` while OPS silently drops the data — exactly what
            # happened to setProductPrice (id:null for all 558 calls)
            # and PC54's setProduct (phantom id:10001).
            result_val = data.get("result")
            is_rejected = (
                result_val is False
                or (isinstance(result_val, str) and result_val.lower() == "false")
            )
            if is_rejected:
                ops_msg = data.get("message") or f"OPS rejected {response_root}"
                raise RuntimeError(f"OPS_REJECTED: {str(ops_msg)[:400]}")
            return data

        return _invoke


class FakeOpsClient:
    """Dry-run client — fabricates IDs and records calls. No OPS traffic."""

    def __init__(self) -> None:
        self.calls: list[dict] = []
        self._counter = 10000

    async def aclose(self) -> None:
        pass

    async def execute(self, query: str, *, variables: dict | None = None) -> OpsResult:
        """Dry-run has no real OPS to query. Report 'no existing product' so the
        dedup path treats every dry-run as a create (mirrors the empty-result
        contract of get_product_by_sku). Prevents the AttributeError that used to
        make dry-run dedup silently no-op."""
        return OpsResult(ok=True, data={"getProductBySku": {}})

    def _next_id(self) -> int:
        self._counter += 1
        return self._counter

    def _record(self, method: str, variables: dict, response: dict) -> None:
        self.calls.append({"method": method, "input": variables, "response": response})

    # All array-input mutations return `id` (matching live OPS contract).
    # _normalize_mutation_response in execute_push aliases `id` to the named
    # field downstream placeholders expect (products_id, size_id, etc.).

    async def set_product_category(self, variables: dict) -> dict:
        r = {"id": self._next_id()}
        self._record("set_product_category", variables, r)
        return r

    async def set_product(self, variables: dict) -> dict:
        r = {"id": self._next_id()}
        self._record("set_product", variables, r)
        return r

    async def set_product_size(self, variables: dict) -> dict:
        r = {"id": self._next_id()}
        self._record("set_product_size", variables, r)
        return r

    async def set_product_price(self, variables: dict) -> dict:
        r = {"id": self._next_id()}
        self._record("set_product_price", variables, r)
        return r

    async def set_assign_options(self, variables: dict) -> dict:
        r = {"id": self._next_id()}
        self._record("set_assign_options", variables, r)
        return r

    async def set_additional_option(self, variables: dict) -> dict:
        r = {"id": self._next_id()}
        self._record("set_additional_option", variables, r)
        return r

    async def set_additional_option_attributes(self, variables: dict) -> dict:
        r = {"id": self._next_id()}
        self._record("set_additional_option_attributes", variables, r)
        return r

    async def set_products_attribute_price(self, variables: dict) -> dict:
        r = {"id": self._next_id()}
        self._record("set_products_attribute_price", variables, r)
        return r

    async def set_products_image_gallery(self, variables: dict) -> dict:
        # Gallery returns {result, message} (no id) — mirror that shape.
        r = {"result": True, "message": "dry-run image gallery ok"}
        self._record("set_products_image_gallery", variables, r)
        return r

    async def update_product_stock(self, variables: dict) -> dict:
        r = {
            "stock_id": self._counter,
            "stock_quantity": (variables.get("input") or {}).get("stock_quantity", 0),
        }
        self._record("update_product_stock", variables, r)
        return r


def _build_live_client(customer: Customer) -> OpsClientAdapter:
    """Hydrate an OpsGraphQLClient from the customer's encrypted ops_auth_config."""
    secret = (customer.ops_auth_config or {}).get("client_secret")
    if not secret:
        raise RuntimeError(
            f"Customer {customer.id} ops_auth_config.client_secret is unset — "
            "live push cannot authenticate"
        )
    auth = OpsAuth(
        base_url=customer.ops_base_url,
        token_url=customer.ops_token_url,
        client_id=customer.ops_client_id,
        client_secret=secret,
    )
    return OpsClientAdapter(OpsGraphQLClient(auth))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Helpers
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _redact_auth(steps: list[dict]) -> list[dict]:
    """Redact Authorization header values before persisting to step_results."""
    out = []
    for step in steps:
        s = dict(step)
        headers = s.get("headers", {})
        if headers:
            s["headers"] = {
                k: ("Bearer ***" if k.lower() == "authorization" else v)
                for k, v in headers.items()
            }
        out.append(s)
    return out


async def _fire_callback(push_log_id: str, callback_url: str, payload: dict) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                callback_url,
                json=payload,
                headers={"X-ApiHub-Event": "push.completed"},
            )
            return r.status_code < 300
    except Exception as e:
        logger.warning("callback failed push_log=%s err=%s", push_log_id, e)
        return False


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Core gateway functions
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def prepare_push_intent(
    req: PushRequest,
    key: IntegrationKey,
    db: AsyncSession,
    idempotency_key: Optional[str] = None,
) -> PushRequestAccepted:
    """Stage 1: validate, idempotency check, preflight, insert push_log row.

    Returns immediately with push_log_id + status=accepted.
    execute_push() is called after this (sync or background).
    """
    customer_id = req.target.customer_id
    supplier_slug = req.source.supplier_slug
    pref = req.product_ref

    # ── Resolve customer ──
    customer = (await db.execute(
        select(Customer).where(Customer.id == customer_id)
    )).scalar_one_or_none()
    if not customer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": f"Customer {customer_id} not found"
        })

    # ── Resolve supplier + product ──
    supplier = (await db.execute(
        select(Supplier).where(Supplier.slug == supplier_slug)
    )).scalar_one_or_none()
    if not supplier:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": f"Supplier '{supplier_slug}' not found"
        })

    # ── Inline product upsert ──
    # When the orchestrator ships the full product inline, upsert it into the
    # catalog first (ON CONFLICT DO UPDATE via persist_product), then fall
    # through to the normal resolve-from-catalog path below. The PushRequest
    # validator already set product_ref.supplier_sku from the inline product,
    # so the resolver finds the just-upserted row by (supplier_sku, supplier_id).
    if req.product is not None:
        # Local import avoids a circular import: catalog.persistence pulls in
        # catalog models that (transitively) import gateway-adjacent modules.
        from modules.catalog.persistence import persist_product
        await persist_product(db, supplier.id, req.product, category_id=None)
        await db.flush()

    # product_ref accepts product_id (UUID) OR supplier_sku — exactly one path
    # must resolve a row. We don't enforce "both unset" at the Pydantic layer so
    # error shape stays consistent with the gateway envelope.
    if pref.product_id is None and not pref.supplier_sku:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail={
            "code": "INVALID_REF",
            "message": "product_ref must include product_id or supplier_sku",
        })

    product_query = select(Product).options(
        selectinload(Product.variants), selectinload(Product.images)
    )
    if pref.product_id is not None:
        product_query = product_query.where(Product.id == pref.product_id)
    else:
        product_query = product_query.where(
            Product.supplier_sku == pref.supplier_sku,
            Product.supplier_id == supplier.id,
        )
    product = (await db.execute(product_query)).scalar_one_or_none()
    if not product:
        identifier = str(pref.product_id) if pref.product_id else pref.supplier_sku
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": f"Product '{identifier}' not found in catalog"
        })

    # Cross-check: if resolved by product_id, the product must belong to the
    # supplier the orchestrator named. Stops a key scoped to "sanmar" from
    # nominating a 4Over product simply by knowing its UUID.
    if pref.product_id is not None and product.supplier_id != supplier.id:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "SUPPLIER_MISMATCH",
            "message": (
                f"Product {product.id} belongs to a different supplier than "
                f"'{supplier_slug}'"
            ),
        })

    supplier_sku = product.supplier_sku

    # ── Optional pre-push sync: re-fetch product from supplier before building payload ──
    if req.sync_before_push:
        try:
            from modules.import_jobs.service import run_import
            from modules.import_jobs.base import DiscoveryMode
            logger.info(
                "sync_before_push: triggering explicit_list sync for %s / %s",
                supplier_slug, supplier_sku,
            )
            # Timeout capped at 10 s (down from 30 s) to prevent worker
            # starvation when multiple sync_before_push requests arrive
            # simultaneously on a 2-worker deployment.
            await asyncio.wait_for(
                run_import(
                    supplier_id=supplier.id,
                    mode=DiscoveryMode.EXPLICIT_LIST,
                    explicit_list=[supplier_sku],
                ),
                timeout=10.0,
            )
            # Re-load in own session so the request-scoped db connection
            # is not held across the full sync duration.
            async with async_session() as own_db:
                fresh = (await own_db.execute(
                    select(Product)
                    .where(Product.id == product.id)
                    .options(selectinload(Product.variants), selectinload(Product.images))
                )).scalar_one_or_none()
            if fresh:
                product = fresh
            logger.info("sync_before_push: sync complete for %s", supplier_sku)
        except asyncio.TimeoutError:
            logger.warning("sync_before_push timed out for %s — pushing with cached data", supplier_sku)
        except Exception as exc:
            logger.warning("sync_before_push failed for %s: %s — pushing with cached data", supplier_sku, exc)

    # ── Compute payload hash over the canonical request body (Rev 1, RFC 8785) ──
    # Task 6: real RFC 8785 JCS hash over the inbound request, not a stub on (product_id, customer_id).
    payload_hash = compute_payload_hash(req.model_dump(mode="json"))

    # ── Idempotency check ──
    existing = (await db.execute(
        select(ProductPushLog).where(
            ProductPushLog.key_id == key.id,
            ProductPushLog.idempotency_key == idempotency_key,
        )
    )).scalar_one_or_none() if idempotency_key else None

    if existing:
        if existing.payload_hash == payload_hash:
            # Same key + same body → return existing (idempotent replay)
            return PushRequestAccepted(
                push_log_id=existing.id,
                status=existing.status,
                customer_id=customer_id,
                supplier_slug=supplier_slug,
                supplier_sku=supplier_sku,
                ops_product_id=existing.ops_product_id,
                dry_run=existing.dry_run,
                callback_status=existing.callback_status,
                created_at=existing.pushed_at,
                links=PushRequestLinks(self=f"/api/integrations/v1/push-requests/{existing.id}"),
            )
        else:
            raise HTTPException(status.HTTP_409_CONFLICT, detail={
                "code": "IDEMPOTENCY_CONFLICT",
                "message": "Same Idempotency-Key was used with a different payload"
            })

    # ── Concurrency guard ──
    in_flight = (await db.execute(
        select(ProductPushLog).where(
            ProductPushLog.customer_id == customer_id,
            ProductPushLog.product_id == product.id,
            ProductPushLog.status == "processing",
        )
    )).scalar_one_or_none()
    if in_flight:
        raise HTTPException(status.HTTP_409_CONFLICT, detail={
            "code": "IN_FLIGHT",
            "message": "Another push for this product is currently processing"
        })

    # ── Preflight (Task 7: 8 real checks + token cache) ──
    preflight = await run_preflight(db, customer_id, product.id, dry_run=req.dry_run)
    if not preflight.ok:
        # Use Task 7's spec-shaped error envelope (status/code/message/details/trace_id).
        envelope = preflight.to_error_envelope()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, detail=envelope)

    # ── Insert push_log row ──
    now = datetime.now(timezone.utc)
    push_log = ProductPushLog(
        product_id=product.id,
        customer_id=customer_id,
        status="accepted",
        pushed_at=now,
        key_id=key.id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        supplier_slug=supplier_slug,
        supplier_sku=supplier_sku,
        callback_url=req.callback.url if req.callback else None,
        callback_status="pending" if req.callback else "not_requested",
        dry_run=req.dry_run,
    )
    db.add(push_log)
    await db.commit()
    await db.refresh(push_log)

    return PushRequestAccepted(
        push_log_id=push_log.id,
        status="accepted",
        customer_id=customer_id,
        supplier_slug=supplier_slug,
        supplier_sku=supplier_sku,
        dry_run=req.dry_run,
        callback_status=push_log.callback_status,
        created_at=push_log.pushed_at,
        links=PushRequestLinks(self=f"/api/integrations/v1/push-requests/{push_log.id}"),
        # run_preflight returns warnings as CheckResult dataclasses — serialize
        # each to a dict for the response schema. (Test mocks may already pass
        # dicts; tolerate both.)
        warnings=[
            w.to_dict() if hasattr(w, "to_dict") else w
            for w in (getattr(preflight, "warnings", []) or [])
        ],
    )


async def execute_push(push_log_id: uuid_mod.UUID) -> None:
    """Stage 2: execute mutation plan against OPS (or FakeOpsClient for dry_run).

    Runs synchronously for ≤20 variants, or as a BackgroundTask for >20.
    Uses its own DB session — safe to run detached from the request session.
    """
    async with async_session() as db:
        push_log = await db.get(ProductPushLog, push_log_id)
        if not push_log:
            logger.error("execute_push: push_log %s not found", push_log_id)
            return

        # ── Atomic transition: accepted → processing ──
        # Only one worker should ever claim a given push_log row. The WHERE
        # clause ensures the transition is idempotent: if two workers race,
        # only the first succeeds; the second sees zero rows updated.
        #
        # Retry behaviour when a prior attempt crashed mid-push and left
        # the row in 'processing':
        #   - Terminal states (pushed / failed / partial_failure / dry_run_pushed):
        #     the push already completed — return silently, nothing to do.
        #   - 'processing': the prior attempt crashed before writing a terminal
        #     state. Raise so arq's retry/DLQ contract engages: subsequent
        #     retries keep raising until the budget is exhausted, at which
        #     point run_push_job calls _finalize_push_log_failed and the row
        #     is marked 'failed'. Without the raise, arq treats the silent
        #     return as success and never retries — the row sticks in
        #     'processing' forever.
        result = await db.execute(
            update(ProductPushLog)
            .where(ProductPushLog.id == push_log_id, ProductPushLog.status == "accepted")
            .values(status="processing")
            .returning(ProductPushLog.id)
        )
        if not result.fetchone():
            # Row was not in 'accepted' — check why before deciding what to do.
            _TERMINAL = {"pushed", "failed", "partial_failure", "dry_run_pushed"}
            if push_log.status in _TERMINAL:
                logger.info(
                    "execute_push: push_log %s already terminal (%s) — skipping",
                    push_log_id, push_log.status,
                )
                return
            # 'processing' (or any unexpected non-terminal state): a prior
            # attempt is stuck. Raise so arq retries and eventually
            # calls _finalize_push_log_failed on exhaustion.
            raise RuntimeError(
                f"execute_push: push_log {push_log_id} is in '{push_log.status}' "
                f"(expected 'accepted') — prior attempt may have crashed; "
                f"arq will retry."
            )
        await db.commit()

        product = (await db.execute(
            select(Product)
            .options(selectinload(Product.variants), selectinload(Product.images))
            .where(Product.id == push_log.product_id)
        )).scalar_one_or_none()
        customer = await db.get(Customer, push_log.customer_id)

        # ── Select client ──
        if push_log.dry_run:
            client: Any = FakeOpsClient()
        else:
            if customer is None:
                logger.error("execute_push: customer %s vanished mid-flight", push_log.customer_id)
                push_log.status = "failed"
                push_log.cleanup_targets = {"reason": "customer not found at execute time"}
                await db.commit()
                return
            try:
                client = _build_live_client(customer)
            except RuntimeError as e:
                logger.error("execute_push: live client unavailable — %s", e)
                push_log.status = "failed"
                push_log.cleanup_targets = {"reason": str(e)}
                await db.commit()
                return

        try:
            # ── Pre-push dedup (P2.2) ─────────────────────────────────────
            # Before building the plan, if we have no push_mapping yet (i.e.
            # we'd otherwise create a new OPS product), ask OPS whether one
            # exists with this SKU. Catches the case where an earlier push
            # wrote to OPS but crashed before persisting the mapping —
            # without this guard, the retry creates a duplicate row in OPS.
            #
            # Skipped for dry-run (FakeOpsClient.GetProductBySku returns the
            # programmed dict so tests can still exercise the dedup path).
            if customer is not None and push_log.supplier_sku:
                existing_mapping = (await db.execute(
                    select(PushMapping).where(
                        PushMapping.source_product_id == push_log.product_id,
                        PushMapping.customer_id == push_log.customer_id,
                    )
                )).scalar_one_or_none()
                if existing_mapping is None or not existing_mapping.target_ops_product_id:
                    raw_client = getattr(client, "_client", client)
                    discovered = await _dedup_lookup_in_ops(raw_client, push_log.supplier_sku)
                    if discovered is not None:
                        logger.info(
                            "dedup: OPS already has products_id=%s for sku=%s — switching to update mode",
                            discovered, push_log.supplier_sku,
                        )
                        await _ensure_push_mapping_for_dedup(
                            db, customer, push_log.product_id,
                            push_log.supplier_sku, discovered,
                        )
                        await db.flush()

            # ── Build mutation plan (Task 6: real builder with markup + RFC 8785) ──
            payload = await build_push_payload(db, push_log.customer_id, push_log.product_id)
            plan = [step.model_dump(mode="json") for step in payload.plan]

            step_results: list[dict] = []
            step_responses: dict[int, dict] = {}
            ops_product_id: Optional[str] = None
            final_status = "pushed" if not push_log.dry_run else "dry_run_pushed"
            cleanup_targets: Optional[dict] = None

            # ── Execute plan sequentially ──
            import hashlib, json as _json
            for step_num, step in enumerate(plan, start=1):
                mutation = step.get("mutation", "")
                raw_variables = step.get("variables", {})
                t_start = datetime.now(timezone.utc)

                # Resolve $stepN.field placeholders to real IDs returned by
                # earlier steps before sending to OPS.
                try:
                    variables = _resolve_placeholders(raw_variables, step_responses)
                except ValueError as e:
                    step_results.append({
                        "step": step_num,
                        "mutation": mutation,
                        "status": "failed",
                        "ops_ids": {},
                        "attempted_at": t_start.isoformat(),
                        "request_fingerprint": "",
                        "error": f"placeholder resolution failed: {e}",
                    })
                    cleanup_targets = {"ops_product_id": ops_product_id, "failed_at": mutation}
                    final_status = "partial_failure" if ops_product_id else "failed"
                    break

                # setProductsImageGallery takes products_id as a top-level Int!
                # arg; OPS returns the setProduct id as a string, which the
                # GraphQL layer rejects for Int!. Coerce numeric strings to int.
                if mutation == "setProductsImageGallery":
                    _pid = variables.get("products_id")
                    if isinstance(_pid, str) and _pid.lstrip("-").isdigit():
                        variables = dict(variables, products_id=int(_pid))

                fingerprint = hashlib.sha256(
                    _json.dumps({"mutation": mutation, "variables": variables}, sort_keys=True).encode()
                ).hexdigest()[:16]
                # Brief throttle between mutations to avoid OPS rate-limiting.
                # 0.1s gives ~10 req/s — fast enough for 1675 steps in ~3 min.
                if step_num > 1:
                    await asyncio.sleep(0.1)

                # ── Phase 6: updateProductStock stock_id resolution ──
                # Strip the gateway-only `_size_id_ref` sentinel (it's not
                # a real OPS arg), then look up the stock_id for that size.
                # OPS's updateProductStock needs stock_id — there is no
                # per-size SKU field anywhere in OPS's schema, so the only
                # way to identify a variant for stock is via stock_id from
                # an existing stock entry. If no entry exists for the size,
                # we skip the step with a clear warning so the operator
                # knows to initialize stock in OPS admin first.
                if mutation == "updateProductStock":
                    size_id_for_lookup = variables.pop("_size_id_ref", None)
                    if size_id_for_lookup is not None:
                        raw_client = getattr(client, "_client", client)
                        stock_id = await _resolve_stock_id_for_size(
                            raw_client,
                            product_id=int(ops_product_id) if ops_product_id else None,
                            size_id=int(size_id_for_lookup),
                        )
                        if stock_id is None:
                            # Initial stock entry doesn't exist in OPS for
                            # this size — record an actionable warning and
                            # move on. OPS API has no way to create one;
                            # admin must initialize via the OPS UI.
                            step_results.append({
                                "step": step_num,
                                "mutation": mutation,
                                "status": "warning",
                                "ops_ids": {},
                                "attempted_at": t_start.isoformat(),
                                "request_fingerprint": fingerprint,
                                "error": (
                                    f"No OPS stock entry exists for size_id={size_id_for_lookup}. "
                                    "Initialize stock for this variant in OPS admin (Stock "
                                    "Management → Add Initial Stock) before re-pushing — OPS's "
                                    "updateProductStock API can only update existing entries."
                                ),
                            })
                            continue
                        # Use the resolved stock_id; drop product_sku if any
                        variables["stock_id"] = stock_id
                        variables.pop("product_sku", None)

                try:
                    method = getattr(client, _mutation_to_method(mutation), None)
                    if method is None:
                        raise NotImplementedError(f"No client method for {mutation}")
                    resp = await method(variables)
                    # All array-input mutations return {index,result,message,id}.
                    # Downstream placeholders use named aliases; add them here.
                    resp = _normalize_mutation_response(mutation, resp)
                    # setProduct may return id=null when the product already exists
                    # in OPS from a prior partial push. Fall back to a SKU lookup.
                    if mutation == "setProduct" and not resp.get("products_id"):
                        raw_client = getattr(client, "_client", client)
                        sku_result = await _m.get_product_by_sku(
                            client=raw_client, products_sku=push_log.supplier_sku
                        )
                        if sku_result.ok and sku_result.data.get("products_id"):
                            resp = dict(resp, products_id=sku_result.data["products_id"])
                            logger.info(
                                "setProduct returned null id — resolved via SKU lookup: %s → products_id=%s",
                                push_log.supplier_sku, resp["products_id"],
                            )
                    step_responses[step_num] = resp
                    if "products_id" in resp and resp["products_id"]:
                        ops_product_id = str(resp["products_id"])
                    ops_ids = {k: str(v) for k, v in resp.items() if k.endswith("_id")}
                    step_results.append({
                        "step": step_num,
                        "mutation": mutation,
                        "status": "ok",
                        "ops_ids": ops_ids,
                        "attempted_at": t_start.isoformat(),
                        "request_fingerprint": fingerprint,
                    })
                except Exception as e:
                    # Stock + image-gallery writes are best-effort. Stock: OPS
                    # exposes no SKU field on ProductSizeInput, so our supplier
                    # SKUs can't be matched. Images: a bad/unreachable URL
                    # shouldn't sink an otherwise-good push. Log these as
                    # warnings but don't abort — the product + sizes + prices
                    # are the critical writes.
                    is_warn_only = mutation in ("updateProductStock", "setProductsImageGallery")
                    step_results.append({
                        "step": step_num,
                        "mutation": mutation,
                        "status": "warning" if is_warn_only else "failed",
                        "ops_ids": {},
                        "attempted_at": t_start.isoformat(),
                        "request_fingerprint": fingerprint,
                        "error": str(e),
                    })
                    if is_warn_only:
                        continue  # keep iterating over remaining stock updates
                    cleanup_targets = {"ops_product_id": ops_product_id, "failed_at": mutation}
                    final_status = "partial_failure" if ops_product_id else "failed"
                    break

            # ── Post-push read-back verify (P2.2.4 — opt-in) ────────────
            # When OPS_POST_PUSH_VERIFY=1, ask OPS to confirm the product
            # we just wrote actually shows up with the expected id.
            # Logs only — never blocks.
            if (
                final_status == "pushed"
                and ops_product_id
                and not push_log.dry_run
                and push_log.supplier_sku
            ):
                await _verify_post_push(getattr(client, "_client", client), push_log.supplier_sku, ops_product_id)

            # ── Persist results ──
            push_log.step_results = _redact_auth(step_results)
            push_log.status = final_status
            push_log.cleanup_targets = cleanup_targets
            # Clear the per-product stock-lookup cache so a later push for
            # the same product sees freshly-initialized stock entries
            # (Phase 6 — admin may have run "Add Initial Stock" between pushes).
            if ops_product_id:
                try:
                    _clear_stock_lookup_cache(int(ops_product_id))
                except (TypeError, ValueError):
                    pass
            # Save ops_product_id for both success and partial_failure so
            # retries can use update mode instead of creating a duplicate product.
            if ops_product_id and final_status in ("pushed", "partial_failure"):
                push_log.ops_product_id = ops_product_id

            # ── Upsert push_mappings (live push only) ──
            # Also record on partial_failure so retries switch to update mode.
            if final_status in ("pushed", "partial_failure") and ops_product_id is not None:
                try:
                    target_int = int(ops_product_id)
                except (TypeError, ValueError):
                    target_int = None
                if target_int is not None:
                    existing_mapping = (await db.execute(
                        select(PushMapping).where(
                            PushMapping.source_product_id == push_log.product_id,
                            PushMapping.customer_id == push_log.customer_id,
                        )
                    )).scalar_one_or_none()
                    now_mapping = datetime.now(timezone.utc)
                    if existing_mapping:
                        existing_mapping.target_ops_product_id = target_int
                        existing_mapping.updated_at = now_mapping
                    else:
                        db.add(PushMapping(
                            source_system="api-hub",
                            source_product_id=push_log.product_id,
                            source_supplier_sku=push_log.supplier_sku,
                            customer_id=push_log.customer_id,
                            target_ops_base_url=(customer.ops_base_url if customer else ""),
                            target_ops_product_id=target_int,
                            pushed_at=now_mapping,
                            updated_at=now_mapping,
                            status="active",
                        ))

                # Update customer-catalog selection
                sel = (await db.execute(
                    select(CustomerProductSelection).where(
                        CustomerProductSelection.customer_id == push_log.customer_id,
                        CustomerProductSelection.product_id == push_log.product_id,
                    )
                )).scalar_one_or_none()
                now = datetime.now(timezone.utc)
                if sel:
                    sel.status = "pushed"
                    sel.pushed_at = now
                else:
                    db.add(CustomerProductSelection(
                        customer_id=push_log.customer_id,
                        product_id=push_log.product_id,
                        status="pushed",
                        added_at=now,
                        pushed_at=now,
                    ))

            await db.commit()

            # ── Fire callback ──
            if push_log.callback_url and push_log.callback_status == "pending":
                success = await _fire_callback(
                    str(push_log_id),
                    push_log.callback_url,
                    {
                        "event": "push.completed",
                        "push_log_id": str(push_log_id),
                        "status": final_status,
                        "ops_product_id": ops_product_id,
                        "supplier_sku": push_log.supplier_sku,
                    },
                )
                push_log.callback_status = "sent" if success else "failed"
                push_log.callback_attempts = 1
                await db.commit()

            # ── Fire outbound webhooks ──
            _webhook_event = (
                "push.completed" if final_status in ("pushed", "dry_run_pushed")
                else "push.partial_failure" if final_status == "partial_failure"
                else "push.failed"
            )
            await fire_webhooks(
                customer_id=push_log.customer_id,
                event=_webhook_event,
                payload={
                    "push_log_id": str(push_log_id),
                    "status": final_status,
                    "ops_product_id": ops_product_id,
                    "supplier_sku": push_log.supplier_sku,
                    "dry_run": push_log.dry_run,
                },
            )
        finally:
            await client.aclose()


# Maps each mutation to the named alias that downstream placeholders use for its `id`.
# OPS returns `id` for all array-input mutations; these are the field names callers expect.
_MUTATION_ID_ALIAS: dict[str, str] = {
    "setProductCategory":            "category_id",
    "setProduct":                    "products_id",
    "setProductSize":                "size_id",
    "setProductPrice":               "product_price_id",
    "setAssignOptions":              "product_option_id",
    "setAdditionalOption":           "prod_add_opt_id",
    "setAdditionalOptionAttributes": "attribute_id",
    "setProductsAttributePrice":     "attribute_id",
    "updateProductStock":            "stock_id",
}


def _normalize_mutation_response(mutation: str, resp: dict) -> dict:
    """Add a named alias for the `id` field returned by OPS array-input mutations."""
    alias = _MUTATION_ID_ALIAS.get(mutation)
    if alias and "id" in resp and alias not in resp:
        resp = dict(resp, **{alias: resp["id"]})
    return resp


def _mutation_to_method(mutation: str) -> str:
    mapping = {
        "setProductCategory":            "set_product_category",
        "setProduct":                    "set_product",
        "setProductSize":                "set_product_size",
        "setProductPrice":               "set_product_price",
        "setAssignOptions":              "set_assign_options",
        "setAdditionalOption":           "set_additional_option",
        "setAdditionalOptionAttributes": "set_additional_option_attributes",
        "setProductsAttributePrice":     "set_products_attribute_price",
        "setProductsImageGallery":       "set_products_image_gallery",
        "updateProductStock":            "update_product_stock",
    }
    return mapping.get(mutation, mutation)


# Matches the placeholder format emitted by payload_builder._placeholder():
# "$step1.products_id", "$step3.size_id", etc.
_PLACEHOLDER_RE = re.compile(r"^\$step(\d+)\.(\w+)$")


def _resolve_placeholders(value: Any, step_responses: dict[int, dict]) -> Any:
    """Recursively replace ``$stepN.field`` strings with the value of ``field``
    from the recorded response of step ``N``.

    The payload builder emits these as forward references when a later step's
    variable depends on an ID returned by an earlier step (e.g.
    ``setProductSize`` needs the ``products_id`` returned by ``setProduct``).
    The fake OPS client ignores variables entirely so dry-runs never noticed,
    but live OPS would receive the literal string and reject it.
    """
    if isinstance(value, str):
        m = _PLACEHOLDER_RE.match(value)
        if not m:
            return value
        step_num = int(m.group(1))
        field = m.group(2)
        resp = step_responses.get(step_num)
        if resp is None:
            raise ValueError(
                f"placeholder {value!r} references step {step_num} which has no recorded response"
            )
        if field not in resp:
            raise ValueError(
                f"placeholder {value!r}: step {step_num} response missing field {field!r}"
            )
        return resp[field]
    if isinstance(value, dict):
        return {k: _resolve_placeholders(v, step_responses) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve_placeholders(v, step_responses) for v in value]
    return value
