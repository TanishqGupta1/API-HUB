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
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import IntegrityError
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
from modules.ops_client.fake import FakeOpsClient
from modules.ops_config.models import OpsCategoryMapping
from modules.ops_push.payload_builder import build_push_payload, compute_payload_hash
from modules.ops_push.preflight import run_preflight
from modules.ops_push.verify import verify_pushed_product
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

    Catches the crash-recovery case: an earlier push wrote the product to OPS
    but died before persisting the push_mapping — without this, the retry would
    create a DUPLICATE. `get_product_by_sku` paginates OPS's `products` query and
    matches on external_ref (= our supplier SKU, written on setProduct) since OPS
    has no server-side SKU filter.

    Defensive: any error (auth, schema mismatch, transport) is logged and
    returns None so the push falls through to its normal create-or-update
    path. We never want a flaky dedup query to BLOCK a legitimate push.

    Returns the OPS products_id when a match exists, else None.
    """
    try:
        result = await _m.find_product_id_by_main_sku(client=client, main_sku=supplier_sku)
    except Exception:  # noqa: BLE001 — defensive
        logger.exception("dedup: find_product_id_by_main_sku raised for sku=%s", supplier_sku)
        return None
    if not result.ok:
        logger.warning(
            "dedup: find_product_id_by_main_sku not OK for sku=%s: %s",
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
        result = await _m.find_product_id_by_main_sku(client=client, main_sku=supplier_sku)
    except Exception:  # noqa: BLE001
        logger.exception("verify: find_product_id_by_main_sku raised for sku=%s", supplier_sku)
        return
    if not result.ok:
        logger.warning(
            "verify: find_product_id_by_main_sku not OK after push sku=%s: %s",
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


async def _verify_b7_readback(ops: Any, ops_product_id: Any) -> None:
    """Full B7 read-back: sizes, stock, images, prices. Opt-in via OPS_POST_PUSH_VERIFY=1.
    Never blocks or raises — logs only."""
    import os as _os
    if _os.getenv("OPS_POST_PUSH_VERIFY", "0") != "1":
        return
    try:
        pid = int(ops_product_id)
    except (TypeError, ValueError):
        logger.warning("verify[B7]: non-numeric ops_product_id=%r, skipping", ops_product_id)
        return
    try:
        report = await verify_pushed_product(ops, pid)
        if not report.get("exists"):
            logger.warning(
                "verify[B7]: product NOT found in OPS after push — products_id=%s", pid
            )
        else:
            logger.info(
                "verify[B7]: products_id=%s sizes=%d stock_rows=%d images=%d prices=%d/%d",
                pid,
                report["size_count"],
                report["stock_rows"],
                report["image_count"],
                report["price_check"]["with_price_rows"],
                report["price_check"]["sizes_sampled"],
            )
    except Exception:
        logger.exception("verify[B7]: raised for products_id=%s", pid)


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
    """
    if product_id is None:
        return None
    # Dry-run path: FakeOpsClient doesn't model productStocks rows — detect via
    # the is_dry_run sentinel instead of duck-typing.
    if getattr(client, "is_dry_run", False):
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


# Per-product cache of the set of valid size_ids from getProductSkuMatrix.
# Populated lazily on the first setProductSku step of a product (one query
# per product per push, not per variant). `None` value = "no matrix /
# unavailable", which the caller treats as "skip validation".
_sku_matrix_cache: dict[int, Optional[set[int]]] = {}


async def _fetch_valid_sku_size_ids(
    client: Any, *, product_id: Optional[int]
) -> Optional[set[int]]:
    """Return the set of size_ids OPS will accept for setProductSku on this
    product, per getProductSkuMatrix (AI-2). Used to validate the SKU batch
    before sending so we don't assign SKUs to slots OPS rejects ("Invalid
    Product SKU"), which would later break updateProductStock.

    Returns None — meaning "skip validation" — when:
      * product_id is unknown,
      * the client is the dry-run Fake (no real matrix to fetch),
      * the matrix query errors, or
      * OPS reports an empty matrix (product not yet indexed; advisory only).

    Defensive: never raises. A flaky matrix query must not block a push.
    """
    if product_id is None:
        return None
    # Dry-run path: FakeOpsClient has no real product to describe — skip.
    if getattr(client, "is_dry_run", False):
        return None
    if product_id not in _sku_matrix_cache:
        try:
            r = await _m.get_product_sku_matrix(client=client, products_id=product_id)
        except Exception:  # noqa: BLE001 — defensive
            logger.exception("sku-matrix: get_product_sku_matrix raised for product_id=%s", product_id)
            _sku_matrix_cache[product_id] = None
            return None
        if not r.ok:
            logger.warning(
                "sku-matrix: get_product_sku_matrix not OK for product_id=%s: %s",
                product_id, r.ops_error_message,
            )
            _sku_matrix_cache[product_id] = None
            return None
        rows = (r.data or {}).get("matrix") or []
        size_ids = {
            int(row["size_id"]) for row in rows if row.get("size_id") is not None
        }
        # An empty matrix is advisory-only: OPS may not have indexed the
        # just-created sizes yet. Treat as "skip validation" rather than
        # dropping every variant.
        _sku_matrix_cache[product_id] = size_ids or None
    return _sku_matrix_cache[product_id]


def _clear_sku_matrix_cache(product_id: int) -> None:
    """Forget the cached SKU matrix for a product after the push."""
    _sku_matrix_cache.pop(product_id, None)


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


# Matches OPS's rejection when an UPDATE targets a products_id that no longer
# exists in OPS (deleted in the admin while our push_mapping still points to it).
# e.g. "OPS_REJECTED: Product with id 556 not found, skipping update."
_PRODUCT_NOT_FOUND_RE = re.compile(r"not found.*skipping update", re.IGNORECASE)


def _force_setproduct_create(variables: dict) -> dict:
    """Return a copy of setProduct variables with products_id forced to 0
    (create mode) on every input row — used by stale-mapping recovery."""
    out = dict(variables)
    inputs = [dict(i) for i in out.get("inputs", [])]
    for i in inputs:
        i["products_id"] = 0
    out["inputs"] = inputs
    return out


async def _clear_stale_mapping(
    db: AsyncSession, customer_id: Any, product_id: Any
) -> None:
    """Delete the push_mapping for (customer, product) after OPS reports the
    mapped product no longer exists. With no mapping, the rebuilt plan runs in
    create mode so the product is recreated instead of failing forever."""
    await db.execute(
        delete(PushMapping).where(
            PushMapping.customer_id == customer_id,
            PushMapping.source_product_id == product_id,
        )
    )
    await db.flush()


def _normalize_category_key(name: str) -> str:
    """Lower-case + collapse whitespace so 'T-Shirts ' and 't-shirts' match."""
    return re.sub(r"\s+", " ", name).strip().lower()[:150]


async def _persist_category_mapping(
    *,
    customer_id: uuid_mod.UUID,
    category_key: str,
    category_name: str,
    ops_category_id: int,
    external_ref: str,
) -> int:
    """Persist the (customer, category_key) → ops_category_id mapping in its OWN
    committed transaction, independent of the caller's request session.

    The OPS category is created as a LIVE side-effect just before this is called.
    The old behaviour added the row to the caller's session and only flushed; any
    later failure in execute_push before its final commit would then roll the
    mapping back while the OPS category persisted — so the next retry would create
    a DUPLICATE category. Committing here makes the mapping durable the instant the
    OPS category exists, so retries reuse it instead of recreating it.

    Concurrency: two simultaneous first-pushes of the same new category can both
    create an OPS category and race to insert the mapping. The unique constraint
    (customer_id, category_key) lets only one row win; the loser catches the
    IntegrityError and returns the winner's ops_category_id so the mapping — our
    source of truth — stays single.
    """
    now = datetime.now(timezone.utc)
    async with async_session() as own_db:
        own_db.add(OpsCategoryMapping(
            customer_id=customer_id,
            category_key=category_key,
            category_name=category_name,
            ops_category_id=ops_category_id,
            external_ref=external_ref,
            created_at=now,
            updated_at=now,
        ))
        try:
            await own_db.commit()
            return ops_category_id
        except IntegrityError:
            await own_db.rollback()
            existing = (await own_db.execute(
                select(OpsCategoryMapping.ops_category_id).where(
                    OpsCategoryMapping.customer_id == customer_id,
                    OpsCategoryMapping.category_key == category_key,
                )
            )).scalar_one_or_none()
            if existing is not None:
                logger.info(
                    "auto-category: lost insert race for key=%s — reusing existing id=%s",
                    category_key, existing,
                )
                return existing
            raise


async def _resolve_ops_category(
    db: AsyncSession,
    client: Any,
    customer: Customer,
    product: Product,
    *,
    dry_run: bool,
) -> Optional[int]:
    """Auto-resolve the OPS category id for `product.category`.

    Looks up our cached (customer, category_key) → ops_category_id mapping; on a
    miss (and only for live pushes) creates the category in OPS once via
    setProductCategory, caches the mapping, and returns the new id. Returns None
    on any failure or for dry-runs with no cached mapping — the builder then
    falls back to the storefront-config / customer-default category, so this can
    never BLOCK a push.
    """
    raw_name = (getattr(product, "category", None) or "").strip()
    if not raw_name:
        return None
    key = _normalize_category_key(raw_name)

    existing = (await db.execute(
        select(OpsCategoryMapping).where(
            OpsCategoryMapping.customer_id == customer.id,
            OpsCategoryMapping.category_key == key,
        )
    )).scalar_one_or_none()
    if existing:
        return existing.ops_category_id

    # Don't create OPS categories during a read-only preview.
    if dry_run:
        return None

    raw_client = getattr(client, "_client", client)
    external_ref = f"apihub:cat:{key}"
    try:
        result = await _m.create_product_category(
            client=raw_client, category_name=raw_name, external_ref=external_ref,
        )
    except Exception:  # noqa: BLE001 — defensive; never block a push
        logger.exception("auto-category: create raised for %r", raw_name)
        return None
    if not result.ok or not (result.data or {}).get("category_id"):
        logger.warning(
            "auto-category: create not OK for %r: %s",
            raw_name, getattr(result, "ops_error_message", None),
        )
        return None
    try:
        cat_id = int(result.data["category_id"])
    except (TypeError, ValueError):
        logger.warning("auto-category: non-numeric id for %r: %r", raw_name, result.data)
        return None

    logger.info("auto-category: created OPS category %r → id=%s", raw_name, cat_id)
    # Persist the mapping in its OWN transaction (not `db`) so it survives even
    # if execute_push raises before its final commit — otherwise the rolled-back
    # mapping would orphan the just-created OPS category → duplicate on retry.
    return await _persist_category_mapping(
        customer_id=customer.id,
        category_key=key,
        category_name=raw_name,
        ops_category_id=cat_id,
        external_ref=external_ref,
    )


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
    "set_product_sku":                 (_m._SET_PRODUCT_SKU,                 "setProductSku"),
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
        call ``find_product_id_by_main_sku``, which calls ``client.execute``).

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
    # Auto-recover orphaned rows: a `processing` push older than 5 minutes is
    # almost certainly dead (worker crashed, backend was reloaded mid-push,
    # OPS hung). Mark them failed so they don't permanently block re-pushes.
    # We do this BEFORE the in-flight check so a stuck row from a prior
    # reload doesn't keep blocking new pushes forever.
    await db.execute(text(
        """
        UPDATE product_push_log
           SET status = 'failed'
         WHERE customer_id = :cid AND product_id = :pid
           AND status IN ('processing', 'accepted', 'queued')
           AND EXTRACT(EPOCH FROM (now() - pushed_at)) > 300
        """
    ), {"cid": customer_id, "pid": product.id})
    await db.commit()

    # Dry-runs are read-only previews. They should never block live pushes,
    # and they shouldn't block each other (the preview page may fire several
    # back-to-back as the user adjusts settings). Only live pushes contend
    # for the same product/customer slot.
    if not req.dry_run:
        in_flight = (await db.execute(
            select(ProductPushLog).where(
                ProductPushLog.customer_id == customer_id,
                ProductPushLog.product_id == product.id,
                ProductPushLog.status == "processing",
                ProductPushLog.dry_run.is_(False),
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


# ── Idempotent re-push cleanup ──────────────────────────────────────────────
# OPS inserts child records (additional options, sizes, gallery images) with
# id=0 on EVERY push, so re-pushing the same product APPENDS duplicate children
# rather than replacing them (verified 2026-06-16: a second push of KP155 left
# 42 options / 2 sizes instead of 21 / 1). On an UPDATE push we therefore delete
# the product's existing children first, then the plan re-creates them fresh.
#
# Only clears the child types the current plan will RE-ADD — e.g. an images-off
# push (no setProductsImageGallery step) must NOT wipe the gallery, or it would
# delete images without restoring them.
_EXISTING_OPTIONS_Q = (
    "query($id:Int){ productAdditionalOptions(products_id:$id, limit:1000)"
    "{ productAdditionalOptions { prod_add_opt_id } } }"
)
_EXISTING_SIZES_Q = (
    "query($id:Int){ productSize(products_id:$id, limit:1000)"
    "{ productSize { size_id } } }"
)
_EXISTING_GALLERY_Q = (
    "query($id:Int){ productsImageGallery(products_id:$id, limit:1000)"
    "{ productsImageGallery { products_image_gallery_id } } }"
)


async def _clear_existing_children(
    raw_client: Any, ops_product_id: int, plan_mutations: set[str]
) -> dict:
    """Delete a product's existing options/sizes/gallery before an update re-adds
    them (idempotent re-push). Best-effort: logs and continues on any failure so
    a cleanup hiccup never blocks the push itself."""
    deleted = {"options": 0, "sizes": 0, "gallery": 0}

    if "setAdditionalOption" in plan_mutations:
        try:
            r = await raw_client.execute(_EXISTING_OPTIONS_Q, variables={"id": ops_product_id})
            rows = ((r.data or {}).get("productAdditionalOptions") or {}).get("productAdditionalOptions") or [] if r.ok else []
            for o in rows:
                oid = o.get("prod_add_opt_id")
                if not oid:
                    continue
                res = await raw_client.execute(
                    _m._SET_ADDITIONAL_OPTION,
                    variables={"inputs": [{"prod_add_opt_id": oid, "products_id": ops_product_id, "delete": 1}]},
                )
                if res.ok:
                    deleted["options"] += 1
                await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning("idempotent cleanup (options) failed for ops_product=%s: %s", ops_product_id, e)

    if "setProductSize" in plan_mutations:
        try:
            r = await raw_client.execute(_EXISTING_SIZES_Q, variables={"id": ops_product_id})
            rows = ((r.data or {}).get("productSize") or {}).get("productSize") or [] if r.ok else []
            for s in rows:
                sid = s.get("size_id")
                if not sid:
                    continue
                res = await raw_client.execute(
                    _m._SET_PRODUCT_SIZE,
                    variables={"inputs": [{"size_id": sid, "products_id": ops_product_id, "delete": 1}]},
                )
                if res.ok:
                    deleted["sizes"] += 1
                await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning("idempotent cleanup (sizes) failed for ops_product=%s: %s", ops_product_id, e)

    if "setProductsImageGallery" in plan_mutations:
        try:
            r = await raw_client.execute(_EXISTING_GALLERY_Q, variables={"id": ops_product_id})
            rows = ((r.data or {}).get("productsImageGallery") or {}).get("productsImageGallery") or [] if r.ok else []
            gids = [g.get("products_image_gallery_id") for g in rows if g.get("products_image_gallery_id")]
            if gids:
                # Gallery deletes batch into one mutation via image_arr.
                res = await raw_client.execute(
                    _m._SET_PRODUCTS_IMAGE_GALLERY,
                    variables={
                        "products_id": ops_product_id,
                        "optimizeimg": 0,
                        "input": {"image_arr": [{"products_image_gallery_id": g, "delete": 1} for g in gids]},
                    },
                )
                if res.ok:
                    deleted["gallery"] = len(gids)
        except Exception as e:
            logger.warning("idempotent cleanup (gallery) failed for ops_product=%s: %s", ops_product_id, e)

    return deleted


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
            # Dry-run uses FakeOpsClient, whose `products` query returns the
            # programmed catalog so tests can still exercise the dedup path.
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

            # ── Auto-category: resolve (and create-on-first-use) the OPS
            # category matching the product's category name, so the product
            # lands in the right storefront category automatically instead of
            # needing a manual pick. Falls back to the customer default on any
            # failure — never blocks the push.
            resolved_category_id: Optional[int] = None
            if customer is not None and product is not None:
                resolved_category_id = await _resolve_ops_category(
                    db, client, customer, product, dry_run=push_log.dry_run
                )

            # ── Build mutation plan (Task 6: real builder with markup + RFC 8785) ──
            # Phase 8 builder references image URLs directly (OPS fetches them
            # server-side with optimizeimg=1) — no slow S3 staging step, so the
            # dry-run preview is already fast and side-effect-free.
            payload = await build_push_payload(
                db, push_log.customer_id, push_log.product_id,
                category_id_override=resolved_category_id,
            )
            plan = [step.model_dump(mode="json") for step in payload.plan]

            # ── Idempotent re-push: clear existing children before re-adding ──
            # On an UPDATE of a product that already exists in OPS, delete its
            # current options/sizes/gallery first so this push REPLACES them
            # instead of appending duplicates. Only clears child types this plan
            # will re-add. Skipped for dry-run (FakeOpsClient / no real product).
            if (
                not push_log.dry_run
                and payload.push_mode == "update"
                and payload.existing_ops_product_id
            ):
                raw_client = getattr(client, "_client", client)
                plan_mutations = {s.get("mutation", "") for s in plan}
                cleared = await _clear_existing_children(
                    raw_client, int(payload.existing_ops_product_id), plan_mutations
                )
                logger.info(
                    "idempotent re-push: cleared existing children for ops_product=%s: %s",
                    payload.existing_ops_product_id, cleared,
                )

            step_results: list[dict] = []
            step_responses: dict[int, dict] = {}
            ops_product_id: Optional[str] = None
            final_status = "pushed" if not push_log.dry_run else "dry_run_pushed"
            cleanup_targets: Optional[dict] = None
            # Guard: only attempt stale-mapping recovery once per push so a
            # persistent OPS rejection can't loop.
            stale_recovery_done = False

            # ── Phase 5: step-resumption — skip steps that already succeeded
            # in a prior partial push for this (customer, product). Looks
            # only at live pushes (dry-runs use a separate FakeOpsClient
            # universe of IDs). Match by source_key, which is stable across
            # plan attempts for the same logical mutation.
            # Map source_key → (prior_push_id, prior_ops_ids, prior_fingerprint).
            # Skip resumption only when the new step's fingerprint matches —
            # if the payload changed (e.g. a new ProductInput field), re-execute.
            prior_ok_by_source_key: dict[str, tuple[uuid_mod.UUID, dict, str]] = {}
            if not push_log.dry_run:
                prior_pushes = (await db.execute(
                    select(ProductPushLog)
                    .where(
                        ProductPushLog.customer_id == push_log.customer_id,
                        ProductPushLog.product_id == push_log.product_id,
                        ProductPushLog.id != push_log_id,
                        ProductPushLog.dry_run.is_(False),
                        ProductPushLog.status.in_(("partial_failure", "failed")),
                    )
                    .order_by(ProductPushLog.pushed_at.desc())
                    .limit(5)
                )).scalars().all()
                seen_keys: set[str] = set()
                for prior in prior_pushes:
                    for s in (prior.step_results or []):
                        if not isinstance(s, dict):
                            continue
                        sk = s.get("source_key")
                        if not sk or sk in seen_keys:
                            continue
                        if s.get("status") == "ok" and s.get("ops_ids"):
                            prior_ok_by_source_key[sk] = (
                                prior.id, s["ops_ids"], s.get("request_fingerprint", "")
                            )
                            seen_keys.add(sk)
                if prior_ok_by_source_key:
                    logger.info(
                        "step-resumption: found %d resumable steps from prior push(es) for product=%s customer=%s",
                        len(prior_ok_by_source_key), push_log.product_id, push_log.customer_id,
                    )

            # ── Execute plan sequentially ──
            import hashlib, json as _json
            for step_num, step in enumerate(plan, start=1):
                mutation = step.get("mutation", "")
                raw_variables = step.get("variables", {})
                source_key = step.get("source_key", "")
                t_start = datetime.now(timezone.utc)

                # Resolve $stepN.field placeholders FIRST so the fingerprint
                # below is over the same shape as prior steps stored. Prior
                # step_responses are already populated (either from a skip-
                # reuse a few lines down, or from a live execute earlier in
                # this loop), so placeholder resolution succeeds.
                try:
                    variables = _resolve_placeholders(raw_variables, step_responses)
                except ValueError as e:
                    step_results.append({
                        "step": step_num,
                        "mutation": mutation,
                        "source_key": source_key,
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
                # Also clear any existing gallery images first so re-pushes don't
                # accumulate duplicates (each setProductsImageGallery with id=0
                # creates a new entry; we must delete the old ones first).
                if mutation == "setProductsImageGallery":
                    _pid = variables.get("products_id")
                    if isinstance(_pid, str) and _pid.lstrip("-").isdigit():
                        _pid = int(_pid)
                        variables = dict(variables, products_id=_pid)
                    if isinstance(_pid, int) and _pid > 0 and not push_log.dry_run:
                        _gal_res = await client.execute(
                            query="{ productsImageGallery(products_id: %d) { productsImageGallery { products_image_gallery_id } } }" % _pid,
                            variables={},
                        )
                        _existing = (
                            (_gal_res.data or {}).get("productsImageGallery", {}) or {}
                        ).get("productsImageGallery") or []
                        if _existing:
                            _del_arr = [
                                {"products_image_gallery_id": _img["products_image_gallery_id"], "delete": 1,
                                 "title": "", "products_large_image_name": "", "sort_order": 0, "status": "0"}
                                for _img in _existing
                            ]
                            _del_mut = (
                                "mutation ClearGallery($pid: Int!, $inp: ProductsImageGalleryBulkInput!) {"
                                " setProductsImageGallery(products_id: $pid, optimizeimg: 0, input: $inp)"
                                " { index result } }"
                            )
                            await client.execute(query=_del_mut, variables={"pid": _pid, "inp": {"image_arr": _del_arr}})
                            logger.info("gallery pre-clear: deleted %d existing images for product %d", len(_existing), _pid)

                # setProductSku: prod_add_opt_ids / attribute_ids are String! in
                # the OPS schema, but placeholders resolve them to ints (the
                # setAdditionalOption*/attribute ids). Coerce each input's
                # option/attribute id fields back to comma-joined strings.
                if mutation == "setProductSku":
                    def _coerce_ids(item: dict) -> dict:
                        out = dict(item)
                        for f in ("prod_add_opt_ids", "attribute_ids"):
                            v = out.get(f)
                            if v is None:
                                continue
                            if isinstance(v, (list, tuple)):
                                out[f] = ",".join(str(x) for x in v)
                            else:
                                out[f] = str(v)
                        return out
                    _inputs = variables.get("inputs")
                    if isinstance(_inputs, list):
                        variables = dict(variables, inputs=[_coerce_ids(i) for i in _inputs])

                    # AI-2: validate the SKU batch against getProductSkuMatrix
                    # — OPS's authoritative list of assignable (size, option)
                    # slots — before sending. Assigning a SKU to a size OPS
                    # doesn't recognize returns "Invalid Product SKU" and
                    # leaves the variant un-stockable. Advisory for now: we
                    # log mismatches but still send (the matrix may lag the
                    # just-created sizes); flip to drop-invalid once verified
                    # live against staging product 602.
                    raw_client = getattr(client, "_client", client)
                    valid_size_ids = await _fetch_valid_sku_size_ids(
                        raw_client,
                        product_id=int(ops_product_id) if ops_product_id else None,
                    )
                    if valid_size_ids is not None:
                        for _i in (variables.get("inputs") or []):
                            _sid = _i.get("size_id")
                            try:
                                _sid_int = int(_sid)
                            except (TypeError, ValueError):
                                continue
                            if _sid_int not in valid_size_ids:
                                logger.warning(
                                    "sku-matrix: size_id=%s for sku=%s not in OPS valid "
                                    "matrix for product_id=%s — SKU may be rejected",
                                    _sid_int, _i.get("sku"), ops_product_id,
                                )

                # setProductSku: prod_add_opt_ids / attribute_ids are String! in
                # the OPS schema, but placeholders resolve them to ints (the
                # setAdditionalOption*/attribute ids). Coerce each input's
                # option/attribute id fields back to comma-joined strings.
                if mutation == "setProductSku":
                    def _coerce_ids(item: dict) -> dict:
                        out = dict(item)
                        for f in ("prod_add_opt_ids", "attribute_ids"):
                            v = out.get(f)
                            if v is None:
                                continue
                            if isinstance(v, (list, tuple)):
                                out[f] = ",".join(str(x) for x in v)
                            else:
                                out[f] = str(v)
                        return out
                    _inputs = variables.get("inputs")
                    if isinstance(_inputs, list):
                        variables = dict(variables, inputs=[_coerce_ids(i) for i in _inputs])

                fingerprint = hashlib.sha256(
                    _json.dumps({"mutation": mutation, "variables": variables}, sort_keys=True).encode()
                ).hexdigest()[:16]

                # Phase 5: step-resumption — skip when source_key AND
                # fingerprint both match a prior successful step. Source_key
                # alone is unsafe: if the payload changed (e.g. a new
                # ProductInput field), the prior result is stale and we
                # must re-execute. Fingerprints are over resolved variables.
                prior_match = prior_ok_by_source_key.get(source_key)
                if prior_match is not None:
                    prior_push_id, prior_ops_ids, prior_fp = prior_match
                    if prior_fp and prior_fp == fingerprint:
                        step_responses[step_num] = dict(prior_ops_ids)
                        if "products_id" in prior_ops_ids and prior_ops_ids["products_id"]:
                            ops_product_id = str(prior_ops_ids["products_id"])
                        step_results.append({
                            "step": step_num,
                            "mutation": mutation,
                            "source_key": source_key,
                            "status": "skipped",
                            "ops_ids": prior_ops_ids,
                            "attempted_at": t_start.isoformat(),
                            "request_fingerprint": prior_fp,
                            "reused_from_push": str(prior_push_id),
                        })
                        continue
                    logger.info(
                        "step-resumption: re-executing step %d source_key=%s — payload changed (prior_fp=%s new_fp=%s)",
                        step_num, source_key, prior_fp, fingerprint,
                    )
                # Brief throttle between mutations to avoid OPS rate-limiting.
                # Skip in dry_run — FakeOpsClient has no rate limit.
                if step_num > 1 and not push_log.dry_run:
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
                                "source_key": source_key,
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

                # Retry loop: attempt the mutation up to _MAX_STEP_ATTEMPTS times.
                # OPS staging sometimes returns a transient empty-error (no message,
                # no status code info) on high-mutation pushes — a short backoff and
                # retry recovers without aborting the whole push.
                _MAX_STEP_ATTEMPTS = 3
                _step_succeeded = False
                _last_exc: Exception | None = None
                for _attempt in range(_MAX_STEP_ATTEMPTS):
                    if _attempt > 0:
                        backoff = 2.0 * _attempt
                        logger.warning(
                            "Step %d %s — retry %d/%d after %.1fs (prev error: %s)",
                            step_num, mutation, _attempt, _MAX_STEP_ATTEMPTS - 1,
                            backoff, repr(_last_exc),
                        )
                        await asyncio.sleep(backoff)
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
                            sku_result = await _m.find_product_id_by_main_sku(
                                client=raw_client, main_sku=push_log.supplier_sku
                            )
                            if sku_result.ok and sku_result.data.get("products_id"):
                                pid = sku_result.data["products_id"]
                                if isinstance(pid, str) and pid.lstrip("-").isdigit():
                                    pid = int(pid)
                                resp = dict(resp, products_id=pid)
                                logger.info(
                                    "setProduct returned null id — resolved via SKU lookup: %s → products_id=%s",
                                    push_log.supplier_sku, resp["products_id"],
                                )
                        # Coerce all numeric-string ID fields to int so downstream
                        # mutations that declare ``*_id: Int!`` never get a string.
                        resp = {
                            k: (int(v) if isinstance(v, str) and v.lstrip("-").isdigit() and k.endswith("_id") else v)
                            for k, v in resp.items()
                        }
                        step_responses[step_num] = resp
                        if "products_id" in resp and resp["products_id"]:
                            ops_product_id = str(resp["products_id"])
                        ops_ids = {k: str(v) for k, v in resp.items() if k.endswith("_id")}
                        step_results.append({
                            "step": step_num,
                            "mutation": mutation,
                            "source_key": source_key,
                            "status": "ok",
                            "ops_ids": ops_ids,
                            "attempted_at": t_start.isoformat(),
                            "request_fingerprint": fingerprint,
                        })
                        _step_succeeded = True
                        break  # success — exit retry loop
                    except Exception as e:
                        _last_exc = e
                        logger.warning(
                            "Step %d %s attempt %d failed — %s: %r",
                            step_num, mutation, _attempt + 1,
                            type(e).__qualname__, str(e),
                        )
                        # OPS rejects an UPDATE with "Product with id N not found"
                        # when the mapped OPS product was deleted in admin but our
                        # push_mappings row still points to it. Clear the stale
                        # mapping and retry setProduct ONCE as a create.
                        if (
                            mutation == "setProduct"
                            and not stale_recovery_done
                            and _PRODUCT_NOT_FOUND_RE.search(str(e))
                        ):
                            stale_recovery_done = True
                            logger.warning(
                                "stale-mapping recovery: %s — clearing mapping for "
                                "product=%s customer=%s and retrying setProduct as create",
                                str(e), push_log.product_id, push_log.customer_id,
                            )
                            await _clear_stale_mapping(db, push_log.customer_id, push_log.product_id)
                            try:
                                create_vars = _force_setproduct_create(variables)
                                resp = _normalize_mutation_response(mutation, await method(create_vars))
                                step_responses[step_num] = resp
                                if resp.get("products_id"):
                                    ops_product_id = str(resp["products_id"])
                                ops_ids = {k: str(v) for k, v in resp.items() if k.endswith("_id")}
                                step_results.append({
                                    "step": step_num,
                                    "mutation": mutation,
                                    "source_key": source_key,
                                    "status": "ok",
                                    "ops_ids": ops_ids,
                                    "attempted_at": t_start.isoformat(),
                                    "request_fingerprint": fingerprint,
                                    "note": "recreated after stale-mapping cleanup",
                                })
                                _step_succeeded = True
                                break
                            except Exception as e_retry:
                                _last_exc = e_retry
                        else:
                            if str(e):
                                break  # non-empty error: don't retry

                if not _step_succeeded:
                    e = _last_exc
                    # Stock + image-gallery writes are best-effort. Stock: OPS
                    # exposes no SKU field on ProductSizeInput, so our supplier
                    # SKUs can't be matched. Images: a bad/unreachable URL
                    # shouldn't sink an otherwise-good push. Log these as
                    # warnings but don't abort — the product + sizes + prices
                    # are the critical writes.
                    is_warn_only = mutation in ("updateProductStock", "setProductsImageGallery")
                    err_str = str(e) if e and str(e) else f"{type(e).__qualname__}(empty)" if e else "unknown"
                    step_results.append({
                        "step": step_num,
                        "mutation": mutation,
                        "source_key": source_key,
                        "status": "warning" if is_warn_only else "failed",
                        "ops_ids": {},
                        "attempted_at": t_start.isoformat(),
                        "request_fingerprint": fingerprint,
                        "error": err_str,
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
                raw_client = getattr(client, "_client", client)
                await _verify_post_push(raw_client, push_log.supplier_sku, ops_product_id)
                await _verify_b7_readback(raw_client, ops_product_id)

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
                    _clear_sku_matrix_cache(int(ops_product_id))
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
    "setProductSku":                 "sku_id",
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
        "setProductSku":                 "set_product_sku",
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
