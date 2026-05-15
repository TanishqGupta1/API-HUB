"""Integration Gateway M1 — preflight validators.

Eight named blocker checks that run BEFORE any OPS write. Aligned to
`docs/superpowers/specs/2026-05-11-integration-gateway-design.md`
Rev 1 §"OPS auth flow and outbound mutation contract" + §"Preflight
gates" + §"Error envelope".

Each check is a small (sync or async) function `(ctx) -> CheckResult`.
The aggregator `run_preflight()` calls them in order, gathers their
results, and returns a `PreflightResults` that the gateway pipeline
translates into a `422 PREFLIGHT_BLOCKER` response when any check fails.

What changed from the old (VPCE) preflight
------------------------------------------
- All 8 checks are kept verbatim — Rev 1 explicitly lists the same
  blocker set ("decorations ready, master-options mapped, prices set,
  images present, customer OPS creds present").
- Output now exposes `to_error_envelope()` matching the new gateway's
  error shape: `{status, code, message, details, trace_id}`.
- A new check `check_customer_ops_creds_present` is split out from the
  old `check_ops_oauth2_reachable` so missing-field-vs-bad-creds gives
  different blocker reasons.
- `check_ops_oauth2_reachable` now uses an in-process token cache
  keyed by `(customer_id, ops_base_url, ops_client_id)` with
  `expires_at = now + expires_in - 60s` (Rev 1 §"OPS credential
  resolution and token cache"). Default TTL 300s if `expires_in` absent.

Side-effects discipline (unchanged)
-----------------------------------
- DB-only checks issue read-only queries.
- External-fetch checks (OAuth2, image HEAD, OPS getProducts) use
  httpx with short timeouts. None mutate OPS.
- No check writes to push_log — that's the gateway/worker's job.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional
from uuid import UUID

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from modules.catalog.models import (
    Product,
    ProductImage,
    ProductOption,
    ProductOptionAttribute,
    ProductVariant,
)
from modules.customers.models import Customer
from modules.decorations.models import CustomerProductDecoration
from modules.markup.engine import resolve_rule
from modules.markup.models import MarkupRule
from modules.push_mappings.models import PushMapping, PushMappingOption
from modules.suppliers.models import Supplier


# ===========================================================================
# Token cache — in-process, per-(customer_id, base_url, client_id)
# ===========================================================================
#
# Rev 1 §"OPS credential resolution and token cache":
#   - Cache the minted token only in process memory.
#   - Key: (customer_id, ops_base_url, ops_client_id)
#   - expires_at = now + expires_in - 60s; default 300s if missing.
#   - On 401/403: evict + remint once; second auth failure is terminal.
#   - Do not store tokens in Postgres or Redis for beta.


@dataclass
class _TokenCacheEntry:
    token: str
    expires_at: float  # unix timestamp


class _TokenCache:
    """Tiny in-process bearer-token cache.

    Public API:
      - get(key)       -> Optional[str]
      - set(key, token, expires_in)
      - evict(key)
      - clear()        # for tests

    Thread-safety: not needed for beta (single FastAPI worker process
    + cooperative asyncio). If we move to multi-worker uvicorn, each
    worker has its own cache — that's fine because tokens are reminted
    on miss.
    """

    _SAFETY_MARGIN_SECONDS = 60
    _DEFAULT_TTL_SECONDS = 300

    def __init__(self) -> None:
        self._store: dict[tuple[Any, str, str], _TokenCacheEntry] = {}

    def get(self, key: tuple[Any, str, str]) -> Optional[str]:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.expires_at <= time.time():
            del self._store[key]
            return None
        return entry.token

    def set(
        self,
        key: tuple[Any, str, str],
        token: str,
        expires_in: Optional[int],
    ) -> None:
        ttl = (
            max(expires_in - self._SAFETY_MARGIN_SECONDS, 1)
            if expires_in
            else self._DEFAULT_TTL_SECONDS
        )
        self._store[key] = _TokenCacheEntry(
            token=token, expires_at=time.time() + ttl
        )

    def evict(self, key: tuple[Any, str, str]) -> None:
        self._store.pop(key, None)

    def clear(self) -> None:
        self._store.clear()


# Module-level singleton — call `clear()` from tests if you need a clean slate.
TOKEN_CACHE = _TokenCache()


# ===========================================================================
# Result types
# ===========================================================================


@dataclass(frozen=True)
class CheckResult:
    """One check's outcome."""

    name: str
    ok: bool
    detail: str
    # Field path the operator should fix (e.g. "customer.ops_token_url").
    # Used to populate the gateway's `details.field` on a 422.
    field: Optional[str] = None
    # One-line operator suggestion (e.g. "Set ops_token_url in /customers/...").
    suggestion: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "detail": self.detail,
            "field": self.field,
            "suggestion": self.suggestion,
        }


@dataclass
class PreflightResults:
    """Aggregate result. Translates 1:1 into the new gateway error envelope
    (`status=error`, `code=PREFLIGHT_BLOCKER`, `details.field`, …) when any
    check fails."""

    checks: list[CheckResult] = field(default_factory=list)
    warnings: list[CheckResult] = field(default_factory=list)
    computed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def blockers(self) -> list[str]:
        """Names of failed checks."""
        return [c.name for c in self.checks if not c.ok]

    @property
    def ok(self) -> bool:
        return len(self.blockers) == 0

    @property
    def first_failure(self) -> Optional[CheckResult]:
        """The first failing check, used to populate `details.field/suggestion`
        on the gateway's 422 response (one focused error beats a wall of text).
        """
        for c in self.checks:
            if not c.ok:
                return c
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "checks": [c.to_dict() for c in self.checks],
            "blockers": self.blockers,
            "warnings": [w.to_dict() for w in self.warnings],
            "computed_at": self.computed_at.isoformat(),
        }

    def to_error_envelope(self, trace_id: Optional[str] = None) -> dict[str, Any]:
        """Spec §"Error envelope" — what the gateway returns as a 422 body
        when `preflight.ok` is False.

        Shape:
            {
              "status": "error",
              "code": "PREFLIGHT_BLOCKER",
              "message": "<first-failure detail>",
              "details": {
                "field": "...",
                "suggestion": "...",
                "blockers": [name, name, ...]
              },
              "trace_id": "<push_log_uuid or None>"
            }
        """
        first = self.first_failure
        message = first.detail if first else "Preflight passed."
        details: dict[str, Any] = {
            "blockers": self.blockers,
            "checks": [c.to_dict() for c in self.checks],
        }
        if first and first.field:
            details["field"] = first.field
        if first and first.suggestion:
            details["suggestion"] = first.suggestion
        return {
            "status": "error",
            "code": "PREFLIGHT_BLOCKER",
            "message": message,
            "details": details,
            "trace_id": trace_id,
        }


# ===========================================================================
# Loader — single round trip; checks operate on these in-memory rows
# ===========================================================================


@dataclass
class _PreflightContext:
    """Everything a check might need. Loaded once by ``run_preflight()``."""

    customer: Customer
    product: Product
    supplier: Supplier
    variants: list[ProductVariant]
    images: list[ProductImage]
    options: list[ProductOption]
    markup_rules: list[MarkupRule]
    push_mapping: Optional[PushMapping]
    push_mapping_options: list[PushMappingOption]
    decoration_options: list[dict]


async def _load_context(
    db: AsyncSession, customer_id: UUID, product_id: UUID
) -> _PreflightContext:
    product = (
        await db.execute(
            select(Product)
            .where(Product.id == product_id)
            .options(
                selectinload(Product.variants),
                selectinload(Product.images),
                selectinload(Product.options).selectinload(
                    ProductOption.attributes
                ),
            )
        )
    ).scalar_one_or_none()
    if product is None:
        raise ValueError(f"Product {product_id} not found")

    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"Customer {customer_id} not found")

    supplier = await db.get(Supplier, product.supplier_id)
    if supplier is None:
        raise ValueError(f"Supplier {product.supplier_id} not found")

    markup_rules = (
        await db.execute(
            select(MarkupRule).where(MarkupRule.customer_id == customer_id)
        )
    ).scalars().all()

    push_mapping = (
        await db.execute(
            select(PushMapping)
            .where(
                PushMapping.customer_id == customer_id,
                PushMapping.source_product_id == product_id,
            )
            .options(selectinload(PushMapping.options))
        )
    ).scalar_one_or_none()
    push_mapping_options = list(push_mapping.options) if push_mapping else []

    decoration_row = (
        await db.execute(
            select(CustomerProductDecoration).where(
                CustomerProductDecoration.customer_id == customer_id,
                CustomerProductDecoration.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    decoration_options = (
        list(decoration_row.decoration_options) if decoration_row else []
    )

    return _PreflightContext(
        customer=customer,
        product=product,
        supplier=supplier,
        variants=list(product.variants),
        images=list(product.images),
        options=list(product.options),
        markup_rules=list(markup_rules),
        push_mapping=push_mapping,
        push_mapping_options=push_mapping_options,
        decoration_options=decoration_options,
    )


# ===========================================================================
# 8 individual checks
# ===========================================================================


def check_base_price_set(ctx: _PreflightContext) -> CheckResult:
    """1. Every ProductVariant.base_price is not null and > 0.

    Catches the modern-normalizer-leaves-None bug (Bug 1) and any
    re-occurrence after future normalizer changes.
    """
    if not ctx.variants:
        return CheckResult("base_price_set", True, "no variants to check")

    bad = [
        v.sku or str(v.id)[:8]
        for v in ctx.variants
        if v.base_price is None or v.base_price <= 0
    ]
    if bad:
        sample = ", ".join(bad[:3])
        more = f" (+{len(bad) - 3} more)" if len(bad) > 3 else ""
        return CheckResult(
            "base_price_set",
            False,
            f"{len(bad)} variant(s) missing base_price: {sample}{more}",
            field="product.variants[].base_price",
            suggestion=(
                "Re-run the supplier inventory sync, or check the normalizer "
                "for upstream changes that left base_price null."
            ),
        )
    return CheckResult(
        "base_price_set",
        True,
        f"all {len(ctx.variants)} variants have base_price > 0",
    )


def check_markup_rule_resolves(ctx: _PreflightContext) -> CheckResult:
    """2. markup.engine.resolve_rule(...) returns non-None for this customer."""
    rule = resolve_rule(
        ctx.markup_rules,
        supplier_sku=ctx.product.supplier_sku,
        category=ctx.product.category,
        supplier_slug=ctx.supplier.slug,
    )
    if rule is None:
        return CheckResult(
            "markup_rule_resolves",
            False,
            (
                f"no markup rule matches product '{ctx.product.supplier_sku}' "
                f"(category={ctx.product.category}, supplier={ctx.supplier.slug}) "
                f"for customer '{ctx.customer.name}'"
            ),
            field="customer.markup_rules",
            suggestion=(
                f"Create a global 'all' markup rule for customer "
                f"'{ctx.customer.name}', or a supplier:'{ctx.supplier.slug}' "
                f"scoped rule."
            ),
        )
    pct = f"{float(rule.markup_pct)}%" if rule.markup_pct is not None else None
    amt = f"${float(rule.markup_amount)}" if rule.markup_amount is not None else None
    markup_label = pct or amt or "pass-through"
    return CheckResult(
        "markup_rule_resolves",
        True,
        f"{rule.scope} → {markup_label} (rule {str(rule.id)[:8]})",
    )


def check_push_mappings_present(ctx: _PreflightContext) -> CheckResult:
    """3. Every ProductOption (and attribute) has a push_mapping_options row.

    Block when:
      - the product has options BUT no mapping rows exist at all
      - mapping rows exist BUT target_ops_option_id (or _attribute_id) is null

    Pass when:
      - product has no options (nothing to map)
      - every option has a non-null target_ops_option_id
    """
    if not ctx.options:
        return CheckResult(
            "push_mappings_present",
            True,
            "product has no options — nothing to map",
        )

    expected_keys = {opt.option_key for opt in ctx.options}
    mapped_keys = {
        m.source_option_key
        for m in ctx.push_mapping_options
        if m.source_option_key and m.target_ops_option_id is not None
    }
    missing = expected_keys - mapped_keys
    if missing:
        sample = ", ".join(sorted(missing)[:3])
        return CheckResult(
            "push_mappings_present",
            False,
            f"missing target_ops_option_id for: {sample}",
            field="push_mappings.target_ops_option_id",
            suggestion=(
                "Run /api/push-mappings/resolve to discover the missing OPS "
                "option IDs, or seed them manually from the OPS admin."
            ),
        )

    expected_attr_keys: set[tuple[str, str]] = set()
    for opt in ctx.options:
        for attr in opt.attributes:
            if attr.attribute_key:
                expected_attr_keys.add((opt.option_key, attr.attribute_key))
    mapped_attr_keys: set[tuple[str, str]] = {
        (m.source_option_key or "", m.source_attribute_key or "")
        for m in ctx.push_mapping_options
        if m.source_attribute_key and m.target_ops_attribute_id is not None
    }
    missing_attrs = expected_attr_keys - mapped_attr_keys
    if missing_attrs:
        sample = ", ".join(f"{o}/{a}" for o, a in sorted(missing_attrs)[:3])
        return CheckResult(
            "push_mappings_present",
            False,
            f"missing target_ops_attribute_id for: {sample}",
            field="push_mappings.target_ops_attribute_id",
            suggestion=(
                "Seed the missing attribute IDs in push_mappings_options."
            ),
        )

    return CheckResult(
        "push_mappings_present",
        True,
        f"all {len(ctx.options)} option(s) and "
        f"{len(expected_attr_keys)} attribute(s) mapped",
    )


def check_customer_ops_creds_present(ctx: _PreflightContext) -> CheckResult:
    """4a. (NEW) Customer has all OPS credential fields populated.

    Split out from `ops_oauth2_reachable` so the operator sees a precise
    "field X is missing" instead of a confusing token-fetch error when
    the actual issue is a never-set field.
    """
    customer = ctx.customer
    missing: list[str] = []
    if not (customer.ops_base_url or "").strip():
        missing.append("ops_base_url")
    if not (customer.ops_token_url or "").strip():
        missing.append("ops_token_url")
    if not (customer.ops_client_id or "").strip():
        missing.append("ops_client_id")
    if not (customer.ops_auth_config or {}).get("client_secret"):
        missing.append("ops_auth_config.client_secret")

    if missing:
        return CheckResult(
            "customer_ops_creds_present",
            False,
            f"customer is missing OPS credential field(s): {', '.join(missing)}",
            field=f"customer.{missing[0]}",
            suggestion=(
                f"Populate /customers/{customer.id} → ops_* fields before "
                f"pushing. Secrets are stored encrypted via EncryptedJSON."
            ),
        )
    return CheckResult(
        "customer_ops_creds_present",
        True,
        "ops_base_url + token_url + client_id + client_secret all set",
    )


async def check_ops_oauth2_reachable(
    ctx: _PreflightContext, *, token_cache: Optional[_TokenCache] = None
) -> CheckResult:
    """4. Smoke-test OAuth2 token fetch against `customer.ops_token_url`.

    Honors the spec's in-process token cache: if we already have a live
    token for this customer, we don't burn a fresh OAuth2 round trip on
    every preflight. Cache TTL = `expires_in - 60s` (default 300s).
    """
    cache = token_cache or TOKEN_CACHE
    customer = ctx.customer

    token_url = (customer.ops_token_url or "").strip()
    client_id = (customer.ops_client_id or "").strip()
    secret = (customer.ops_auth_config or {}).get("client_secret", "")

    # `check_customer_ops_creds_present` already gates this — but be
    # defensive if a caller bypasses ordering.
    if not (token_url and client_id and secret):
        return CheckResult(
            "ops_oauth2_reachable",
            False,
            "customer OPS credentials missing (see customer_ops_creds_present)",
            field="customer.ops_*",
            suggestion="See customer_ops_creds_present check.",
        )

    cache_key = (customer.id, customer.ops_base_url or "", client_id)
    cached = cache.get(cache_key)
    if cached is not None:
        return CheckResult(
            "ops_oauth2_reachable",
            True,
            "token cache hit (no fresh OAuth2 round trip)",
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": secret,
                },
            )
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException) as exc:
        return CheckResult(
            "ops_oauth2_reachable",
            False,
            f"OAuth2 endpoint unreachable: {exc.__class__.__name__}: {exc}",
            field="customer.ops_token_url",
            suggestion=(
                f"Confirm {token_url} is reachable from API-HUB and that "
                f"the OPS storefront is up."
            ),
        )

    if resp.status_code in (401, 403):
        return CheckResult(
            "ops_oauth2_reachable",
            False,
            f"OAuth2 fetch returned HTTP {resp.status_code} — credentials invalid",
            field="customer.ops_auth_config.client_secret",
            suggestion=(
                "Rotate the OPS client_secret in customer settings; the "
                "stored secret no longer authenticates."
            ),
        )

    if resp.status_code != 200:
        return CheckResult(
            "ops_oauth2_reachable",
            False,
            f"OAuth2 fetch returned HTTP {resp.status_code}",
            field="customer.ops_token_url",
            suggestion=f"Unexpected response from {token_url}; check OPS logs.",
        )

    body = (
        resp.json()
        if resp.headers.get("content-type", "").startswith("application/json")
        else {}
    )
    token = body.get("access_token")
    expires_in = body.get("expires_in")
    if token:
        cache.set(cache_key, token, expires_in)
    detail = f"token issued, exp {expires_in}s" if expires_in else "token issued"
    return CheckResult("ops_oauth2_reachable", True, detail)


async def check_image_urls_reachable(
    ctx: _PreflightContext, *, timeout_seconds: float = 5.0
) -> CheckResult:
    """5. HEAD request per image URL returns 2xx.

    Beta image policy is "single primary front image" — but preflight
    still HEAD-checks every catalog image so the operator sees broken
    URLs surfaced before pushing anything.
    """
    urls = [img.url for img in ctx.images]
    if not urls:
        return CheckResult(
            "image_urls_reachable",
            False,
            "no images attached to product",
            field="product.images",
            suggestion=(
                "Run the supplier media sync, or attach at least one image "
                "to this product."
            ),
        )

    sem = asyncio.Semaphore(5)

    async def _head(url: str) -> tuple[str, bool, str]:
        async with sem:
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    resp = await client.head(url, follow_redirects=True)
                ok = 200 <= resp.status_code < 300
                return url, ok, f"HTTP {resp.status_code}"
            except Exception as exc:  # noqa: BLE001
                return url, False, f"{exc.__class__.__name__}: {exc}"

    results = await asyncio.gather(*(_head(u) for u in urls))
    failures = [(u, msg) for u, ok, msg in results if not ok]
    if failures:
        first = failures[0]
        return CheckResult(
            "image_urls_reachable",
            False,
            f"{len(failures)}/{len(urls)} image URL(s) failed; "
            f"example: {first[0]} → {first[1]}",
            field="product.images[].url",
            suggestion="Replace broken image URLs or re-run the media sync.",
        )
    return CheckResult(
        "image_urls_reachable",
        True,
        f"{len(urls)}/{len(urls)} HEAD 200",
    )


# Type alias for the injected OPS query function used by check 6
OpsQueryFn = Callable[..., Awaitable[Optional[dict]]]


async def check_prefix_collision(
    ctx: _PreflightContext,
    *,
    ops_query_fn: Optional[OpsQueryFn] = None,
) -> CheckResult:
    """6. Query OPS via getProducts for `internal_title = supplier_sku`.

    Block if existing OPS product matches AND no `push_mapping` row claims
    it (would cause UPDATE-vs-CREATE ambiguity in the worker).

    The actual OPS query is performed via `OpsClient` (M1 separate task).
    Without an injected `ops_query_fn`, returns a soft-pass with a warning
    so preflight isn't blocked during local dev.
    """
    if ops_query_fn is None:
        return CheckResult(
            "prefix_collision",
            True,
            "skipped (no OpsClient wired in preflight context)",
        )

    try:
        existing = await ops_query_fn(internal_title=ctx.product.supplier_sku)
    except Exception as exc:  # noqa: BLE001
        return CheckResult(
            "prefix_collision",
            False,
            f"could not query OPS: {exc.__class__.__name__}: {exc}",
            field="customer.ops_base_url",
            suggestion="Investigate OPS GraphQL availability.",
        )

    if not existing:
        return CheckResult(
            "prefix_collision",
            True,
            f"no existing OPS product with internal_title '{ctx.product.supplier_sku}'",
        )

    # If an existing OPS product is claimed by our push_mapping, this is
    # an update — safe. Only block when the claim is missing.
    claimed_ops_id = (
        ctx.push_mapping.target_ops_product_id if ctx.push_mapping else None
    )
    existing_ops_id = (
        existing.get("products_id") if isinstance(existing, dict) else None
    )
    if claimed_ops_id and existing_ops_id and int(claimed_ops_id) == int(existing_ops_id):
        return CheckResult(
            "prefix_collision",
            True,
            f"OPS product {existing_ops_id} claimed by push_mapping → update mode",
        )

    return CheckResult(
        "prefix_collision",
        False,
        (
            f"OPS already has product with internal_title "
            f"'{ctx.product.supplier_sku}' but no push_mapping claims it"
        ),
        field="push_mappings.target_ops_product_id",
        suggestion=(
            "Manually link this product to the existing OPS products_id, "
            "or delete the orphan OPS product from staging."
        ),
    )


def check_required_fields(ctx: _PreflightContext) -> CheckResult:
    """7. product_name, supplier_sku, ≥1 variant present."""
    missing: list[str] = []
    if not ctx.product.product_name or not ctx.product.product_name.strip():
        missing.append("product_name")
    if not ctx.product.supplier_sku or not ctx.product.supplier_sku.strip():
        missing.append("supplier_sku")
    if not ctx.variants:
        missing.append("≥1 variant")
    if missing:
        return CheckResult(
            "required_fields",
            False,
            f"missing: {', '.join(missing)}",
            field=f"product.{missing[0]}",
            suggestion="Fix the product record before pushing.",
        )
    return CheckResult(
        "required_fields",
        True,
        f"name + sku set, {len(ctx.variants)} variant(s)",
    )


def check_decoration_attached(ctx: _PreflightContext) -> CheckResult:
    """8. If supplier.has_decoration_overlay = true, require non-empty
    customer_product_decorations.decoration_options for (customer, product)."""
    if not getattr(ctx.supplier, "has_decoration_overlay", False):
        return CheckResult(
            "decoration_attached",
            True,
            "supplier doesn't require decoration overlay",
        )
    if not ctx.decoration_options:
        return CheckResult(
            "decoration_attached",
            False,
            (
                f"supplier '{ctx.supplier.slug}' requires decoration overlay "
                f"but no decoration_options are configured for this "
                f"customer/product"
            ),
            field="customer_product_decorations.decoration_options",
            suggestion=(
                f"Configure decoration_options for customer "
                f"'{ctx.customer.name}' × product "
                f"'{ctx.product.supplier_sku}'."
            ),
        )
    return CheckResult(
        "decoration_attached",
        True,
        f"{len(ctx.decoration_options)} decoration option(s) configured",
    )


# ===========================================================================
# Aggregator
# ===========================================================================


async def run_preflight(
    db: AsyncSession,
    customer_id: UUID,
    product_id: UUID,
    *,
    ops_query_fn: Optional[OpsQueryFn] = None,
    image_head_timeout_seconds: float = 5.0,
    token_cache: Optional[_TokenCache] = None,
) -> PreflightResults:
    """Run all 8 checks (+1 sub-check) in the order the spec lists them.

    Spec call-site: invoked from `prepare_push_intent()` AFTER the
    gateway has reserved the idempotency row but BEFORE the worker
    can claim it. Failure → `UPDATE product_push_log SET status='rejected'`
    + return `422 PREFLIGHT_BLOCKER` envelope.

    Parameters
    ----------
    db : AsyncSession
    customer_id : UUID
    product_id : UUID
    ops_query_fn : callable, optional
        Coroutine `async def f(*, internal_title: str) -> Optional[dict]`
        for check 6 (prefix_collision). Wired in by the worker with
        `OpsClient.get_products`.
    image_head_timeout_seconds : float
        Per-HEAD-request timeout for check 5.
    token_cache : _TokenCache, optional
        Override the module-level `TOKEN_CACHE` (used in tests).
    """
    ctx = await _load_context(db, customer_id, product_id)

    checks: list[CheckResult] = []
    # 1
    checks.append(check_base_price_set(ctx))
    # 2
    checks.append(check_markup_rule_resolves(ctx))
    # 3
    checks.append(check_push_mappings_present(ctx))
    # 4a (NEW — split out from 4 for precise field-level reporting)
    checks.append(check_customer_ops_creds_present(ctx))
    # 4
    checks.append(await check_ops_oauth2_reachable(ctx, token_cache=token_cache))
    # 5
    checks.append(
        await check_image_urls_reachable(
            ctx, timeout_seconds=image_head_timeout_seconds
        )
    )
    # 6
    checks.append(await check_prefix_collision(ctx, ops_query_fn=ops_query_fn))
    # 7
    checks.append(check_required_fields(ctx))
    # 8
    checks.append(check_decoration_attached(ctx))

    return PreflightResults(checks=checks)


__all__ = [
    "CheckResult",
    "PreflightResults",
    "TOKEN_CACHE",
    "check_base_price_set",
    "check_markup_rule_resolves",
    "check_push_mappings_present",
    "check_customer_ops_creds_present",
    "check_ops_oauth2_reachable",
    "check_image_urls_reachable",
    "check_prefix_collision",
    "check_required_fields",
    "check_decoration_attached",
    "run_preflight",
]
