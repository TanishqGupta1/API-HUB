# Phase 4 — Pricing API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a supplier-agnostic pricing engine — `POST /api/pricing/quote` (anonymous) and `POST /api/customers/{customer_id}/pricing/quote` (markup-aware) — that resolves apparel prices via `variant_prices` lookup and print prices via formula evaluation, returning a deterministic `unit_price` + `total` + `breakdown` trace.

**Architecture:** New `modules/pricing/` module owns two strategy classes — `TieredVariantResolver` for apparel and `FormulaResolver` for print — selected by `product.pricing_method`. Both implement an `async resolve(...)` method returning a typed `QuoteResult` (Pydantic). The HTTP layer is two thin FastAPI routers; the customer-aware route wraps the base resolver, then applies the existing `markup_rules` engine + per-product `product_storefront_configs.pricing_overrides`. Validation (qty > 0, dimensions in `print_details.width_min/max`/`height_min/max`) lives in the resolver, not the route.

**Tech Stack:** FastAPI, async SQLAlchemy 2.0 + asyncpg, PostgreSQL, Pydantic v2, `decimal.Decimal` for all money math (never float), pytest + pytest-asyncio. Inserts in tests use `persist_product` (Phase 1 contract) so the data layer is exercised end-to-end. `Decimal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)` for cent-precision rounding, mirroring `modules/markup/engine.py`.

**Spec:** `docs/superpowers/specs/2026-04-29-multi-supplier-product-model-design.md` (§9 Pricing API + §11.3 pricing tests + §12 Phase 4).

**Depends on:** Phase 1 plan (`docs/superpowers/plans/2026-04-29-polymorphic-product-model-foundation.md`) — schema + `persist_product` + ingest schemas must be merged first.

**Out of scope (other plans):** Frontend price preview UI (Phase 5), live inventory price re-validation, multi-currency conversion (USD only), caching layer.

---

## File Structure

### Files to create
- `backend/modules/pricing/__init__.py`
- `backend/modules/pricing/schemas.py` — Pydantic request/response models (`QuoteRequest`, `QuoteResult`, `CustomerQuoteResult`, breakdown dataclasses)
- `backend/modules/pricing/errors.py` — `PricingError`, `BoundsError`, `MissingPricingDataError`
- `backend/modules/pricing/resolvers.py` — `BaseResolver`, `TieredVariantResolver`, `FormulaResolver`, `resolve_quote(...)` dispatch
- `backend/modules/pricing/customer_quote.py` — markup + storefront-override wrapper
- `backend/modules/pricing/routes.py` — `/api/pricing/quote` + `/api/customers/{customer_id}/pricing/quote`
- `backend/tests/test_pricing_apparel.py` — apparel resolver + endpoint tests
- `backend/tests/test_pricing_print.py` — print resolver + bounds + endpoint tests
- `backend/tests/test_pricing_customer.py` — customer-aware endpoint + markup + override tests

### Files to modify
- `backend/main.py` — import + register the new router

### Files NOT touched
- `backend/modules/markup/engine.py` — reused as-is (`resolve_rule` + `apply_markup`)
- `backend/modules/catalog/persistence.py` — Phase 1 contract; only consumed in tests
- `frontend/**` — Phase 5
- `backend/modules/promostandards/**`, `backend/modules/ops/**` — adapters land in Phases 2/3

---

## Task Breakdown

### Task 1: Create the pricing module skeleton + Pydantic schemas

**Files:**
- Create: `backend/modules/pricing/__init__.py`
- Create: `backend/modules/pricing/schemas.py`
- Create: `backend/modules/pricing/errors.py`
- Test: `backend/tests/test_pricing_apparel.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pricing_apparel.py
"""Pricing API — apparel resolver + endpoint."""
from __future__ import annotations

from decimal import Decimal

import pytest


def test_quote_request_accepts_apparel_payload():
    from modules.pricing.schemas import QuoteRequest

    req = QuoteRequest(
        product_id="00000000-0000-0000-0000-000000000001",
        variant_id="00000000-0000-0000-0000-000000000002",
        qty=50,
    )
    assert req.qty == 50
    assert req.variant_id is not None


def test_quote_request_accepts_print_payload():
    from modules.pricing.schemas import QuoteRequest

    req = QuoteRequest(
        product_id="00000000-0000-0000-0000-000000000001",
        width=Decimal("24"),
        height=Decimal("36"),
        qty=10,
        selected_attribute_ids=["00000000-0000-0000-0000-000000000003"],
    )
    assert req.width == Decimal("24")
    assert req.height == Decimal("36")
    assert req.selected_attribute_ids == ["00000000-0000-0000-0000-000000000003"]


def test_quote_request_rejects_zero_qty():
    from pydantic import ValidationError
    from modules.pricing.schemas import QuoteRequest
    with pytest.raises(ValidationError):
        QuoteRequest(product_id="00000000-0000-0000-0000-000000000001", qty=0)


def test_pricing_errors_are_distinct():
    from modules.pricing.errors import (
        BoundsError,
        MissingPricingDataError,
        PricingError,
    )
    assert issubclass(BoundsError, PricingError)
    assert issubclass(MissingPricingDataError, PricingError)
    assert BoundsError is not MissingPricingDataError
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_pricing_apparel.py -v`
Expected: FAILS — `ImportError: No module named 'modules.pricing'`.

- [ ] **Step 3: Create `__init__.py`**

Create `backend/modules/pricing/__init__.py`:

```python
"""Polymorphic pricing engine — apparel tiered lookup + print formula."""
```

- [ ] **Step 4: Create `errors.py`**

Create `backend/modules/pricing/errors.py`:

```python
"""Per-quote pricing errors. The HTTP layer maps these to 4xx responses."""


class PricingError(Exception):
    """Base for pricing errors that should surface as 4xx, not 5xx."""


class BoundsError(PricingError):
    """Width/height/qty fell outside the bounds declared on the product."""


class MissingPricingDataError(PricingError):
    """Required pricing data (variant, prices, formula) is not on disk."""
```

- [ ] **Step 5: Create `schemas.py`**

Create `backend/modules/pricing/schemas.py`:

```python
"""Pricing API request/response models.

`QuoteRequest` is shared by both apparel and print paths; resolvers ignore
fields they do not consume. The endpoint validates only what Pydantic can
check from the body in isolation (qty > 0, dimensions are non-negative).
Cross-field validation (variant exists, dimensions in bounds, etc.) lives
in the resolver against the database.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, ConfigDict


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: UUID
    variant_id: Optional[UUID] = None              # apparel only
    width: Optional[Decimal] = Field(default=None, ge=0)
    height: Optional[Decimal] = Field(default=None, ge=0)
    qty: int = Field(gt=0)
    selected_attribute_ids: list[UUID] = Field(default_factory=list)


class TierMatch(BaseModel):
    group: str
    qty_band: str                                  # e.g. "13-2147483647"
    tier_price: Decimal


class OptionMultiplierTrace(BaseModel):
    option_key: str
    attribute_key: Optional[str] = None
    multiplier: Decimal


class ApparelBreakdown(BaseModel):
    base: Decimal
    tier_match: Optional[TierMatch] = None
    qty: int
    fallback: bool = False                          # True when no tier matched


class PrintBreakdown(BaseModel):
    base: Decimal
    area: Decimal                                   # width * height
    area_factor: Decimal                            # per-sq-unit multiplier
    option_multipliers: list[OptionMultiplierTrace] = Field(default_factory=list)
    setup_cost: Decimal = Decimal("0")
    qty: int


class QuoteResult(BaseModel):
    unit_price: Decimal
    total: Decimal
    currency: str = "USD"
    breakdown: ApparelBreakdown | PrintBreakdown


class CustomerQuoteResult(QuoteResult):
    """Quote with markup + storefront overrides applied on top of the base."""
    base_unit_price: Decimal
    markup_pct: Optional[Decimal] = None
    rounding: Optional[str] = None
    storefront_override_applied: bool = False
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_pricing_apparel.py -v`
Expected: 4 PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/modules/pricing/__init__.py backend/modules/pricing/errors.py backend/modules/pricing/schemas.py backend/tests/test_pricing_apparel.py
git commit -m "feat(pricing): scaffold module + request/response schemas"
```

---

### Task 2: `BaseResolver` interface + `resolve_quote` dispatch

**Files:**
- Create: `backend/modules/pricing/resolvers.py`
- Test: `backend/tests/test_pricing_apparel.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_pricing_apparel.py`:

```python
@pytest.mark.asyncio
async def test_resolve_quote_dispatches_by_pricing_method(
    db, seed_supplier
):
    """Unknown pricing_method raises MissingPricingDataError."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ApparelDetailsIngest, ProductIngest
    from modules.pricing.errors import MissingPricingDataError
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session

    payload = ProductIngest(
        supplier_sku="DISPATCH-1",
        product_name="dispatch test",
        product_type="apparel",
        pricing_method=None,                          # <- not set
        apparel_details=ApparelDetailsIngest(),
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = product.id

    async with async_session() as s:
        with pytest.raises(MissingPricingDataError, match="pricing_method"):
            await resolve_quote(QuoteRequest(product_id=pid, qty=1), s)
        await s.execute(
            __import__("sqlalchemy").delete(
                __import__("modules.catalog.models", fromlist=["Product"]).Product
            ).where(
                __import__("modules.catalog.models", fromlist=["Product"]).Product.id == pid
            )
        )
        await s.commit()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest tests/test_pricing_apparel.py::test_resolve_quote_dispatches_by_pricing_method -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_quote'`.

- [ ] **Step 3: Create `resolvers.py` skeleton**

Create `backend/modules/pricing/resolvers.py`:

```python
"""Pricing resolvers — strategy per product.pricing_method.

`resolve_quote` is the single entry point. It loads the product, picks a
resolver, and returns a typed `QuoteResult`. Each resolver is responsible
for its own validation against the database (variant existence, bounds,
formula presence, etc.).
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product

from .errors import MissingPricingDataError, PricingError
from .schemas import QuoteRequest, QuoteResult

CENT = Decimal("0.01")


def _to_cents(value: Decimal) -> Decimal:
    """Quantize to two decimal places, banker's-half-up."""
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


class BaseResolver(Protocol):
    async def resolve(
        self, req: QuoteRequest, product: Product, db: AsyncSession
    ) -> QuoteResult: ...


async def resolve_quote(
    req: QuoteRequest, db: AsyncSession
) -> QuoteResult:
    product = await db.get(Product, req.product_id)
    if product is None:
        raise MissingPricingDataError(f"Product {req.product_id} not found")
    resolver = _resolver_for(product)
    return await resolver.resolve(req, product, db)


def _resolver_for(product: Product) -> BaseResolver:
    method = product.pricing_method
    if method == "tiered_variants":
        from .resolvers_apparel import TieredVariantResolver
        return TieredVariantResolver()
    if method == "formula":
        from .resolvers_print import FormulaResolver
        return FormulaResolver()
    raise MissingPricingDataError(
        f"product.pricing_method={method!r} has no resolver"
    )
```

The split into `resolvers_apparel.py` / `resolvers_print.py` keeps each strategy in its own file (Tasks 3 + 5).

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest tests/test_pricing_apparel.py::test_resolve_quote_dispatches_by_pricing_method -v`
Expected: PASS — `pricing_method=None` raises `MissingPricingDataError`.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/pricing/resolvers.py backend/tests/test_pricing_apparel.py
git commit -m "feat(pricing): resolver dispatch by product.pricing_method"
```

---

### Task 3: `TieredVariantResolver` (apparel)

**Files:**
- Create: `backend/modules/pricing/resolvers_apparel.py`
- Test: `backend/tests/test_pricing_apparel.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_pricing_apparel.py`:

```python
@pytest.mark.asyncio
async def test_apparel_resolver_picks_tier_for_qty(db, seed_supplier):
    """qty=1 hits the qty_min=1 tier, qty=144 hits the qty_max=2147483647 tier."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import (
        ApparelDetailsIngest,
        PriceTier,
        ProductIngest,
        VariantIngest,
    )
    from modules.catalog.models import Product, ProductVariant
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import (
        ApparelBreakdown,
        QuoteRequest,
    )
    from database import async_session
    from sqlalchemy import select, delete

    payload = ProductIngest(
        supplier_sku="TIER-1",
        product_name="tiered apparel",
        product_type="apparel",
        pricing_method="tiered_variants",
        apparel_details=ApparelDetailsIngest(apparel_style="Mens"),
        variants=[
            VariantIngest(
                part_id="V-TIER-1",
                color="Black",
                size="L",
                base_price=Decimal("8.00"),
                prices=[
                    PriceTier(group_name="Net", qty_min=1, qty_max=11, price=Decimal("12.50")),
                    PriceTier(group_name="Net", qty_min=12, qty_max=143, price=Decimal("11.00")),
                    PriceTier(group_name="Net", qty_min=144, qty_max=2147483647, price=Decimal("9.50")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = product.id
        variant_id = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()

    async with async_session() as s:
        result1 = await resolve_quote(
            QuoteRequest(product_id=pid, variant_id=variant_id, qty=1), s
        )
        assert result1.unit_price == Decimal("12.50")
        assert result1.total == Decimal("12.50")
        assert isinstance(result1.breakdown, ApparelBreakdown)
        assert result1.breakdown.tier_match.group == "Net"
        assert result1.breakdown.tier_match.qty_band == "1-11"
        assert result1.breakdown.fallback is False

        result144 = await resolve_quote(
            QuoteRequest(product_id=pid, variant_id=variant_id, qty=144), s
        )
        assert result144.unit_price == Decimal("9.50")
        assert result144.total == Decimal("1368.00")
        assert result144.breakdown.tier_match.qty_band == "144-2147483647"

        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_apparel_resolver_falls_back_to_base_price(db, seed_supplier):
    """No variant_prices rows -> falls back to variant.base_price; breakdown notes fallback."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import (
        ApparelDetailsIngest,
        ProductIngest,
        VariantIngest,
    )
    from modules.catalog.models import Product, ProductVariant
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select, delete

    payload = ProductIngest(
        supplier_sku="FALLBACK-1",
        product_name="fallback apparel",
        product_type="apparel",
        pricing_method="tiered_variants",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="V-FB",
                color="White",
                size="M",
                base_price=Decimal("7.25"),
                prices=[],                       # <- empty
            ),
        ],
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = product.id
        variant_id = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()

    async with async_session() as s:
        result = await resolve_quote(
            QuoteRequest(product_id=pid, variant_id=variant_id, qty=10), s
        )
        assert result.unit_price == Decimal("7.25")
        assert result.total == Decimal("72.50")
        assert result.breakdown.fallback is True
        assert result.breakdown.tier_match is None

        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_apparel_resolver_requires_variant_id(db, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ApparelDetailsIngest, ProductIngest
    from modules.catalog.models import Product
    from modules.pricing.errors import MissingPricingDataError
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import delete

    payload = ProductIngest(
        supplier_sku="NEED-VID",
        product_name="need variant",
        product_type="apparel",
        pricing_method="tiered_variants",
        apparel_details=ApparelDetailsIngest(),
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = product.id

    async with async_session() as s:
        with pytest.raises(MissingPricingDataError, match="variant_id"):
            await resolve_quote(QuoteRequest(product_id=pid, qty=1), s)
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_pricing_apparel.py -v`
Expected: 3 new FAILS — `ImportError: cannot import name 'TieredVariantResolver'`.

- [ ] **Step 3: Implement the apparel resolver**

Create `backend/modules/pricing/resolvers_apparel.py`:

```python
"""Apparel pricing — variant_prices tier lookup with base_price fallback."""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product, ProductVariant, VariantPrice

from .errors import MissingPricingDataError
from .resolvers import _to_cents
from .schemas import (
    ApparelBreakdown,
    QuoteRequest,
    QuoteResult,
    TierMatch,
)


class TieredVariantResolver:
    async def resolve(
        self, req: QuoteRequest, product: Product, db: AsyncSession
    ) -> QuoteResult:
        if req.variant_id is None:
            raise MissingPricingDataError(
                "apparel quote requires variant_id"
            )

        variant = await db.get(ProductVariant, req.variant_id)
        if variant is None or variant.product_id != product.id:
            raise MissingPricingDataError(
                f"Variant {req.variant_id} not found on product {product.id}"
            )

        tier = await self._best_tier(variant.id, req.qty, db)
        base = Decimal(variant.base_price) if variant.base_price is not None else None

        if tier is not None:
            unit_price = _to_cents(tier.price)
            tier_match = TierMatch(
                group=tier.group_name,
                qty_band=f"{tier.qty_min}-{tier.qty_max}",
                tier_price=unit_price,
            )
            fallback = False
        elif base is not None:
            unit_price = _to_cents(base)
            tier_match = None
            fallback = True
        else:
            raise MissingPricingDataError(
                f"Variant {variant.id} has no variant_prices and no base_price"
            )

        total = _to_cents(unit_price * Decimal(req.qty))
        return QuoteResult(
            unit_price=unit_price,
            total=total,
            currency="USD",
            breakdown=ApparelBreakdown(
                base=_to_cents(base) if base is not None else unit_price,
                tier_match=tier_match,
                qty=req.qty,
                fallback=fallback,
            ),
        )

    async def _best_tier(
        self, variant_id, qty: int, db: AsyncSession
    ) -> VariantPrice | None:
        """Return the tier whose [qty_min, qty_max] band contains qty.

        If multiple tiers match (e.g. MSRP + Net both cover the same band),
        prefer Net > Sale > MSRP > Case > others alphabetical.
        """
        rows = (await db.execute(
            select(VariantPrice).where(
                VariantPrice.variant_id == variant_id,
                VariantPrice.qty_min <= qty,
                VariantPrice.qty_max >= qty,
            )
        )).scalars().all()
        if not rows:
            return None

        priority = {"Net": 0, "Sale": 1, "MSRP": 2, "Case": 3}
        rows.sort(key=lambda r: (priority.get(r.group_name, 99), r.group_name))
        return rows[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_pricing_apparel.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/pricing/resolvers_apparel.py backend/tests/test_pricing_apparel.py
git commit -m "feat(pricing): apparel TieredVariantResolver with base_price fallback"
```

---

### Task 4: `FormulaResolver` (print) — base × area × multipliers + setup costs

**Files:**
- Create: `backend/modules/pricing/resolvers_print.py`
- Create: `backend/tests/test_pricing_print.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pricing_print.py`:

```python
"""Pricing API — print formula resolver + bounds."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import delete, select


@pytest.mark.asyncio
async def test_print_resolver_evaluates_formula(db, seed_supplier):
    """24x36 banner with three multipliers + setup cost evaluates correctly."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import (
        OptionAttributeIngest,
        OptionIngest,
        PrintDetailsIngest,
        ProductIngest,
        ProductSizeIngest,
    )
    from modules.catalog.models import (
        Product,
        ProductOption,
        ProductOptionAttribute,
    )
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import PrintBreakdown, QuoteRequest
    from database import async_session

    payload = ProductIngest(
        supplier_sku="DECAL-PRICED",
        product_name="Decals - General Performance",
        product_type="print",
        pricing_method="formula",
        print_details=PrintDetailsIngest(
            ops_product_id_int=131,
            width_min=Decimal("1"),
            width_max=Decimal("96"),
            height_min=Decimal("1"),
            height_max=Decimal("96"),
            formula={"base": "1.50", "area_factor": "0.04", "base_setup": "0"},
        ),
        sizes=[
            ProductSizeIngest(
                ops_size_id=160,
                size_title="Custom Size",
                size_width=Decimal("0"),
                size_height=Decimal("0"),
            ),
        ],
        options=[
            OptionIngest(
                option_key="lamMaterial",
                title="Laminate",
                options_type="combo",
                attributes=[
                    OptionAttributeIngest(
                        title="GF - Concept 240",
                        sort_order=1,
                        multiplier=Decimal("1.10"),
                        setup_cost=Decimal("0"),
                    ),
                ],
            ),
            OptionIngest(
                option_key="inkFinish",
                title="Ink Finish",
                options_type="combo",
                attributes=[
                    OptionAttributeIngest(
                        title="FLX",
                        sort_order=3,
                        multiplier=Decimal("0"),
                        setup_cost=Decimal("10.00"),
                    ),
                ],
            ),
        ],
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = product.id

        # collect the two attribute ids the test will pass in
        rows = (await s.execute(
            select(ProductOptionAttribute.id, ProductOptionAttribute.title)
            .join(ProductOption, ProductOption.id == ProductOptionAttribute.product_option_id)
            .where(ProductOption.product_id == pid)
        )).all()
        attr_ids = [r.id for r in rows]
        assert len(attr_ids) == 2

    async with async_session() as s:
        result = await resolve_quote(
            QuoteRequest(
                product_id=pid,
                width=Decimal("24"),
                height=Decimal("36"),
                qty=10,
                selected_attribute_ids=attr_ids,
            ),
            s,
        )

    # Math:
    #   area      = 24 * 36 = 864
    #   unit      = base 1.50 * (area * area_factor 0.04) * lam_multiplier 1.10
    #             = 1.50 * 34.56 * 1.10 = 57.024
    #   per-unit  = 57.024  -> rounds to 57.02
    #   total     = 57.02 * 10 + setup_cost 10.00 = 580.20
    assert result.unit_price == Decimal("57.02")
    assert result.total == Decimal("580.20")
    assert isinstance(result.breakdown, PrintBreakdown)
    assert result.breakdown.area == Decimal("864")
    assert result.breakdown.area_factor == Decimal("0.04")
    assert result.breakdown.setup_cost == Decimal("10.00")
    assert any(o.option_key == "lamMaterial" for o in result.breakdown.option_multipliers)

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_print_resolver_rejects_dimension_below_bounds(db, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import PrintDetailsIngest, ProductIngest
    from modules.catalog.models import Product
    from modules.pricing.errors import BoundsError
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session

    payload = ProductIngest(
        supplier_sku="BOUNDS-1",
        product_name="bounded decal",
        product_type="print",
        pricing_method="formula",
        print_details=PrintDetailsIngest(
            width_min=Decimal("1"),
            width_max=Decimal("96"),
            height_min=Decimal("1"),
            height_max=Decimal("96"),
            formula={"base": "1.50", "area_factor": "0.04"},
        ),
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = product.id

    async with async_session() as s:
        with pytest.raises(BoundsError, match="width"):
            await resolve_quote(
                QuoteRequest(
                    product_id=pid,
                    width=Decimal("0.5"),
                    height=Decimal("10"),
                    qty=1,
                ),
                s,
            )
        with pytest.raises(BoundsError, match="height"):
            await resolve_quote(
                QuoteRequest(
                    product_id=pid,
                    width=Decimal("10"),
                    height=Decimal("999"),
                    qty=1,
                ),
                s,
            )
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_print_resolver_requires_dimensions(db, seed_supplier):
    """Width / height are mandatory for print products."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import PrintDetailsIngest, ProductIngest
    from modules.catalog.models import Product
    from modules.pricing.errors import BoundsError
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session

    payload = ProductIngest(
        supplier_sku="NEED-DIMS",
        product_name="needs dims",
        product_type="print",
        pricing_method="formula",
        print_details=PrintDetailsIngest(formula={"base": "1.50", "area_factor": "0.04"}),
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = product.id

    async with async_session() as s:
        with pytest.raises(BoundsError, match="width.*required"):
            await resolve_quote(QuoteRequest(product_id=pid, qty=1), s)
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_print_resolver_missing_formula_errors(db, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import PrintDetailsIngest, ProductIngest
    from modules.catalog.models import Product
    from modules.pricing.errors import MissingPricingDataError
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session

    payload = ProductIngest(
        supplier_sku="NO-FORMULA",
        product_name="no formula",
        product_type="print",
        pricing_method="formula",
        print_details=PrintDetailsIngest(formula=None),
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = product.id

    async with async_session() as s:
        with pytest.raises(MissingPricingDataError, match="formula"):
            await resolve_quote(
                QuoteRequest(product_id=pid, width=Decimal("1"),
                             height=Decimal("1"), qty=1),
                s,
            )
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_pricing_print.py -v`
Expected: FAIL — `ImportError: cannot import name 'FormulaResolver'`.

- [ ] **Step 3: Implement the print resolver**

Create `backend/modules/pricing/resolvers_print.py`:

```python
"""Print pricing — base * area * Σ multipliers + Σ setup_cost.

Formula JSONB shape on print_details.formula:
  {
    "base":         "1.50",      # base unit price
    "area_factor":  "0.04",      # multiplier per unit area
    "base_setup":   "0.00",      # one-time setup added to total
    "qty_break":    [             # optional, monotonic step discounts
       {"qty_min": 50, "discount": "0.95"},
       {"qty_min": 250, "discount": "0.90"}
    ]
  }
"""
from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import (
    PrintDetails,
    Product,
    ProductOption,
    ProductOptionAttribute,
)

from .errors import BoundsError, MissingPricingDataError
from .resolvers import _to_cents
from .schemas import (
    OptionMultiplierTrace,
    PrintBreakdown,
    QuoteRequest,
    QuoteResult,
)


class FormulaResolver:
    async def resolve(
        self, req: QuoteRequest, product: Product, db: AsyncSession
    ) -> QuoteResult:
        details = await db.get(PrintDetails, product.id)
        if details is None or not details.formula:
            raise MissingPricingDataError(
                f"Print product {product.id} has no formula"
            )

        if req.width is None:
            raise BoundsError("width is required for print products")
        if req.height is None:
            raise BoundsError("height is required for print products")

        self._check_bounds(req.width, req.height, details)

        formula = details.formula
        base = Decimal(str(formula["base"]))
        area_factor = Decimal(str(formula.get("area_factor", "0")))
        base_setup = Decimal(str(formula.get("base_setup", "0")))

        attrs = await self._load_attributes(req.selected_attribute_ids, product.id, db)
        multipliers: list[OptionMultiplierTrace] = []
        unit = base
        unit *= req.width * req.height * area_factor
        for opt_key, attr in attrs:
            mult = Decimal(str(attr.multiplier or 0))
            if mult > 0:
                unit *= mult
                multipliers.append(OptionMultiplierTrace(
                    option_key=opt_key,
                    attribute_key=attr.attribute_key or attr.title,
                    multiplier=mult,
                ))

        unit = self._apply_qty_break(unit, req.qty, formula.get("qty_break"))
        unit_price = _to_cents(unit)

        setup = base_setup + sum(
            (Decimal(str(a.setup_cost or 0)) for _, a in attrs),
            start=Decimal("0"),
        )
        total = _to_cents(unit_price * Decimal(req.qty) + setup)

        return QuoteResult(
            unit_price=unit_price,
            total=total,
            currency="USD",
            breakdown=PrintBreakdown(
                base=_to_cents(base),
                area=req.width * req.height,
                area_factor=area_factor,
                option_multipliers=multipliers,
                setup_cost=_to_cents(setup),
                qty=req.qty,
            ),
        )

    def _check_bounds(
        self, width: Decimal, height: Decimal, details: PrintDetails
    ) -> None:
        if details.width_min is not None and width < Decimal(details.width_min):
            raise BoundsError(
                f"width {width} below minimum {details.width_min}"
            )
        if details.width_max is not None and width > Decimal(details.width_max):
            raise BoundsError(
                f"width {width} above maximum {details.width_max}"
            )
        if details.height_min is not None and height < Decimal(details.height_min):
            raise BoundsError(
                f"height {height} below minimum {details.height_min}"
            )
        if details.height_max is not None and height > Decimal(details.height_max):
            raise BoundsError(
                f"height {height} above maximum {details.height_max}"
            )

    async def _load_attributes(
        self,
        attribute_ids: list,
        product_id,
        db: AsyncSession,
    ) -> list[tuple[str, ProductOptionAttribute]]:
        """Load (option_key, attribute) for every selected_attribute_id.

        Each attribute must belong to a ProductOption owned by `product_id`,
        otherwise it is silently dropped (supplied but not on this product).
        """
        if not attribute_ids:
            return []
        rows = (await db.execute(
            select(ProductOption.option_key, ProductOptionAttribute)
            .join(
                ProductOption,
                ProductOption.id == ProductOptionAttribute.product_option_id,
            )
            .where(
                ProductOptionAttribute.id.in_(attribute_ids),
                ProductOption.product_id == product_id,
            )
        )).all()
        return [(row[0], row[1]) for row in rows]

    def _apply_qty_break(
        self,
        unit: Decimal,
        qty: int,
        qty_break: list | None,
    ) -> Decimal:
        if not qty_break:
            return unit
        # Sort descending by qty_min so the largest matching break wins.
        sorted_breaks = sorted(qty_break, key=lambda b: int(b["qty_min"]), reverse=True)
        for b in sorted_breaks:
            if qty >= int(b["qty_min"]):
                return unit * Decimal(str(b["discount"]))
        return unit
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_pricing_print.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/pricing/resolvers_print.py backend/tests/test_pricing_print.py
git commit -m "feat(pricing): print FormulaResolver + bounds + qty break"
```

---

### Task 5: HTTP route `POST /api/pricing/quote`

**Files:**
- Create: `backend/modules/pricing/routes.py`
- Modify: `backend/main.py` (import + register router)
- Test: `backend/tests/test_pricing_apparel.py`, `backend/tests/test_pricing_print.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_pricing_apparel.py`:

```python
@pytest.mark.asyncio
async def test_pricing_endpoint_apparel_happy_path(client, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import (
        ApparelDetailsIngest,
        PriceTier,
        ProductIngest,
        VariantIngest,
    )
    from modules.catalog.models import Product, ProductVariant
    from database import async_session
    from sqlalchemy import select, delete

    payload = ProductIngest(
        supplier_sku="EP-APRL",
        product_name="endpoint apparel",
        product_type="apparel",
        pricing_method="tiered_variants",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="EPV1",
                color="Black",
                size="L",
                base_price=Decimal("8.00"),
                prices=[
                    PriceTier(group_name="Net", qty_min=1, qty_max=2147483647, price=Decimal("12.50")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = str(product.id)
        vid = str((await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == product.id)
        )).scalar_one())

    resp = await client.post(
        "/api/pricing/quote",
        json={"product_id": pid, "variant_id": vid, "qty": 50},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["unit_price"] == "12.50"
    assert body["total"] == "625.00"
    assert body["currency"] == "USD"
    assert body["breakdown"]["tier_match"]["group"] == "Net"

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id.cast_value(pid) if False else Product.id == product.id))
        await s.commit()


@pytest.mark.asyncio
async def test_pricing_endpoint_returns_404_for_unknown_product(client):
    resp = await client.post(
        "/api/pricing/quote",
        json={
            "product_id": "00000000-0000-0000-0000-000000000000",
            "qty": 1,
        },
    )
    assert resp.status_code == 404
    assert "not found" in resp.text.lower()


@pytest.mark.asyncio
async def test_pricing_endpoint_validates_qty(client):
    resp = await client.post(
        "/api/pricing/quote",
        json={
            "product_id": "00000000-0000-0000-0000-000000000000",
            "qty": 0,
        },
    )
    assert resp.status_code == 422
```

Append to `backend/tests/test_pricing_print.py`:

```python
@pytest.mark.asyncio
async def test_pricing_endpoint_print_returns_400_for_out_of_bounds(client, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import PrintDetailsIngest, ProductIngest
    from modules.catalog.models import Product
    from database import async_session
    from sqlalchemy import delete

    payload = ProductIngest(
        supplier_sku="EP-BOUNDS",
        product_name="bounded ep",
        product_type="print",
        pricing_method="formula",
        print_details=PrintDetailsIngest(
            width_min=Decimal("1"),
            width_max=Decimal("96"),
            height_min=Decimal("1"),
            height_max=Decimal("96"),
            formula={"base": "1.50", "area_factor": "0.04"},
        ),
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = str(product.id)

    resp = await client.post(
        "/api/pricing/quote",
        json={
            "product_id": pid,
            "width": "0.25",
            "height": "10",
            "qty": 1,
        },
    )
    assert resp.status_code == 400
    assert "width" in resp.text.lower()

    async with async_session() as s:
        await s.execute(delete(Product).where(Product.id == product.id))
        await s.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_pricing_apparel.py::test_pricing_endpoint_apparel_happy_path tests/test_pricing_apparel.py::test_pricing_endpoint_returns_404_for_unknown_product tests/test_pricing_apparel.py::test_pricing_endpoint_validates_qty tests/test_pricing_print.py::test_pricing_endpoint_print_returns_400_for_out_of_bounds -v`
Expected: 4 FAILS — route not registered (404) or import error.

- [ ] **Step 3: Create `routes.py`**

Create `backend/modules/pricing/routes.py`:

```python
"""Pricing API routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db

from .errors import BoundsError, MissingPricingDataError
from .resolvers import resolve_quote
from .schemas import QuoteRequest, QuoteResult

router = APIRouter(prefix="/api/pricing", tags=["pricing"])


@router.post("/quote", response_model=QuoteResult)
async def quote(
    req: QuoteRequest, db: AsyncSession = Depends(get_db)
) -> QuoteResult:
    try:
        return await resolve_quote(req, db)
    except BoundsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MissingPricingDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
```

- [ ] **Step 4: Register the router in `main.py`**

Open `backend/main.py`. After the existing `from modules.ops_config.routes import router as ops_config_router` import, add:

```python
from modules.pricing.routes import router as pricing_router
```

After the existing `app.include_router(ops_config_router)`, add:

```python
app.include_router(pricing_router)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_pricing_apparel.py tests/test_pricing_print.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/pricing/routes.py backend/main.py backend/tests/test_pricing_apparel.py backend/tests/test_pricing_print.py
git commit -m "feat(pricing): POST /api/pricing/quote endpoint"
```

---

### Task 6: Customer-aware quote — markup wrapper

**Files:**
- Create: `backend/modules/pricing/customer_quote.py`
- Test: `backend/tests/test_pricing_customer.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_pricing_customer.py`:

```python
"""Customer-aware pricing — markup + storefront overrides."""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import delete


@pytest.mark.asyncio
async def test_customer_quote_applies_customer_markup(db, seed_supplier):
    """A 25% all-scope markup raises a $12.50 unit price to $15.625 -> $15.63."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import (
        ApparelDetailsIngest,
        PriceTier,
        ProductIngest,
        VariantIngest,
    )
    from modules.catalog.models import Product, ProductVariant
    from modules.customers.models import Customer
    from modules.markup.models import MarkupRule
    from modules.pricing.customer_quote import customer_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select

    payload = ProductIngest(
        supplier_sku="CMK-1",
        product_name="customer markup",
        product_type="apparel",
        pricing_method="tiered_variants",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="CMK-V1",
                color="Black",
                size="L",
                base_price=Decimal("8.00"),
                prices=[
                    PriceTier(group_name="Net", qty_min=1, qty_max=2147483647, price=Decimal("12.50")),
                ],
            ),
        ],
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        customer = Customer(
            name="Acme",
            ops_base_url="https://test.ops.com",
            ops_token_url="https://test.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(customer)
        await s.flush()
        rule = MarkupRule(
            customer_id=customer.id,
            scope="all",
            markup_pct=Decimal("25.00"),
            rounding="none",
            priority=0,
        )
        s.add(rule)
        await s.commit()
        pid = product.id
        vid = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()
        cust_id = customer.id

    async with async_session() as s:
        result = await customer_quote(
            cust_id, QuoteRequest(product_id=pid, variant_id=vid, qty=1), s
        )
        assert result.base_unit_price == Decimal("12.50")
        assert result.unit_price == Decimal("15.63")
        assert result.markup_pct == Decimal("25.00")
        assert result.storefront_override_applied is False

        await s.execute(delete(Product).where(Product.id == pid))
        await s.execute(delete(Customer).where(Customer.id == cust_id))
        await s.commit()


@pytest.mark.asyncio
async def test_customer_quote_falls_back_to_base_when_no_markup(db, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import (
        ApparelDetailsIngest,
        PriceTier,
        ProductIngest,
        VariantIngest,
    )
    from modules.catalog.models import Product, ProductVariant
    from modules.customers.models import Customer
    from modules.pricing.customer_quote import customer_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select

    payload = ProductIngest(
        supplier_sku="NO-MK",
        product_name="no markup",
        product_type="apparel",
        pricing_method="tiered_variants",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="NMV1",
                color="W",
                size="M",
                prices=[PriceTier(price=Decimal("9.99"))],
            ),
        ],
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        customer = Customer(
            name="No Markup Co",
            ops_base_url="https://test.ops.com",
            ops_token_url="https://test.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(customer)
        await s.commit()
        pid = product.id
        vid = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()
        cust_id = customer.id

    async with async_session() as s:
        result = await customer_quote(
            cust_id, QuoteRequest(product_id=pid, variant_id=vid, qty=1), s
        )
        assert result.base_unit_price == Decimal("9.99")
        assert result.unit_price == Decimal("9.99")
        assert result.markup_pct is None

        await s.execute(delete(Product).where(Product.id == pid))
        await s.execute(delete(Customer).where(Customer.id == cust_id))
        await s.commit()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_pricing_customer.py -v`
Expected: FAIL — `ImportError: cannot import name 'customer_quote'`.

- [ ] **Step 3: Implement `customer_quote.py`**

Create `backend/modules/pricing/customer_quote.py`:

```python
"""Customer-aware quote — base resolver + markup + storefront overrides."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product
from modules.customers.models import Customer
from modules.markup.engine import apply_markup, resolve_rule
from modules.markup.models import MarkupRule

from .errors import MissingPricingDataError
from .resolvers import _to_cents, resolve_quote
from .schemas import CustomerQuoteResult, QuoteRequest


async def customer_quote(
    customer_id: UUID, req: QuoteRequest, db: AsyncSession
) -> CustomerQuoteResult:
    """Resolve a quote, then apply this customer's markup + storefront overrides.

    Order of operations:
      1. Run the supplier-agnostic resolver (apparel or print).
      2. Look up `markup_rules` rows for the customer; pick best by scope.
      3. Apply markup_pct + rounding (mirrors modules/markup/engine.apply_markup).
      4. Apply per-product `product_storefront_configs.pricing_overrides` last.
    """
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise MissingPricingDataError(f"Customer {customer_id} not found")

    base = await resolve_quote(req, db)

    product = await db.get(Product, req.product_id)
    rules = (await db.execute(
        select(MarkupRule).where(MarkupRule.customer_id == customer_id)
    )).scalars().all()
    rule = resolve_rule(
        rules,
        supplier_sku=product.supplier_sku,
        category=product.category,
    )

    base_unit = base.unit_price
    marked_up = apply_markup(base_unit, rule) or base_unit

    storefront_unit, override_applied = await _apply_storefront_override(
        req.product_id, customer_id, marked_up, db
    )

    unit_price = _to_cents(storefront_unit)
    total = _to_cents(unit_price * Decimal(req.qty))

    return CustomerQuoteResult(
        unit_price=unit_price,
        total=total,
        currency=base.currency,
        breakdown=base.breakdown,
        base_unit_price=base_unit,
        markup_pct=Decimal(str(rule.markup_pct)) if rule else None,
        rounding=rule.rounding if rule else None,
        storefront_override_applied=override_applied,
    )


async def _apply_storefront_override(
    product_id: UUID,
    customer_id: UUID,
    current_unit: Decimal,
    db: AsyncSession,
) -> tuple[Decimal, bool]:
    """Apply pricing_overrides JSONB from product_storefront_configs.

    Supported override keys:
      - "fixed_unit_price": Decimal-string — replaces the marked-up price wholesale
      - "extra_markup_pct": Decimal-string — added on top of marked-up price
      - "rounding":         "nearest_99" | "nearest_dollar" | "none"
    """
    from modules.ops_config.models import ProductStorefrontConfig

    cfg = (await db.execute(
        select(ProductStorefrontConfig).where(
            ProductStorefrontConfig.product_id == product_id,
            ProductStorefrontConfig.customer_id == customer_id,
        )
    )).scalar_one_or_none()
    if cfg is None or not cfg.pricing_overrides:
        return current_unit, False

    overrides = cfg.pricing_overrides
    new_unit = current_unit

    if "fixed_unit_price" in overrides:
        return Decimal(str(overrides["fixed_unit_price"])), True

    if "extra_markup_pct" in overrides:
        pct = Decimal(str(overrides["extra_markup_pct"]))
        new_unit = new_unit * (Decimal("1") + pct / Decimal("100"))

    if overrides.get("rounding") == "nearest_99":
        import math
        new_unit = Decimal(math.floor(new_unit)) + Decimal("0.99")
    elif overrides.get("rounding") == "nearest_dollar":
        new_unit = Decimal(round(new_unit))

    return new_unit, True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_pricing_customer.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/pricing/customer_quote.py backend/tests/test_pricing_customer.py
git commit -m "feat(pricing): customer-aware quote with markup + storefront overrides"
```

---

### Task 7: HTTP route `POST /api/customers/{customer_id}/pricing/quote`

**Files:**
- Modify: `backend/modules/pricing/routes.py`
- Test: `backend/tests/test_pricing_customer.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_pricing_customer.py`:

```python
@pytest.mark.asyncio
async def test_customer_quote_endpoint_happy_path(client, seed_supplier):
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import (
        ApparelDetailsIngest,
        PriceTier,
        ProductIngest,
        VariantIngest,
    )
    from modules.catalog.models import Product, ProductVariant
    from modules.customers.models import Customer
    from modules.markup.models import MarkupRule
    from database import async_session
    from sqlalchemy import select

    payload = ProductIngest(
        supplier_sku="EP-CMK",
        product_name="endpoint customer markup",
        product_type="apparel",
        pricing_method="tiered_variants",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="ECMV1",
                color="Black",
                size="L",
                prices=[PriceTier(price=Decimal("10.00"))],
            ),
        ],
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        customer = Customer(
            name="Acme EP",
            ops_base_url="https://test2.ops.com",
            ops_token_url="https://test2.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(customer)
        await s.flush()
        s.add(MarkupRule(
            customer_id=customer.id,
            scope="all",
            markup_pct=Decimal("50.00"),
            rounding="none",
            priority=0,
        ))
        await s.commit()
        pid = str(product.id)
        vid = str((await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == product.id)
        )).scalar_one())
        cust_id = str(customer.id)

    resp = await client.post(
        f"/api/customers/{cust_id}/pricing/quote",
        json={"product_id": pid, "variant_id": vid, "qty": 4},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["base_unit_price"] == "10.00"
    assert body["unit_price"] == "15.00"
    assert body["total"] == "60.00"
    assert body["markup_pct"] == "50.00"


@pytest.mark.asyncio
async def test_customer_quote_endpoint_unknown_customer(client):
    resp = await client.post(
        "/api/customers/00000000-0000-0000-0000-000000000000/pricing/quote",
        json={
            "product_id": "00000000-0000-0000-0000-000000000000",
            "qty": 1,
        },
    )
    assert resp.status_code == 404
    assert "customer" in resp.text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && pytest tests/test_pricing_customer.py::test_customer_quote_endpoint_happy_path tests/test_pricing_customer.py::test_customer_quote_endpoint_unknown_customer -v`
Expected: FAIL — route 404 because not registered.

- [ ] **Step 3: Add the customer route**

In `backend/modules/pricing/routes.py`, append:

```python
from uuid import UUID

from .customer_quote import customer_quote as _customer_quote
from .schemas import CustomerQuoteResult


@router.post(
    "/customers/{customer_id}/quote",
    response_model=CustomerQuoteResult,
)
async def customer_quote_endpoint(
    customer_id: UUID,
    req: QuoteRequest,
    db: AsyncSession = Depends(get_db),
) -> CustomerQuoteResult:
    try:
        return await _customer_quote(customer_id, req, db)
    except BoundsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MissingPricingDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
```

To match the spec route shape `/api/customers/{customer_id}/pricing/quote`, register a second router on the customers prefix in this file:

```python
customer_router = APIRouter(
    prefix="/api/customers", tags=["pricing"]
)


@customer_router.post(
    "/{customer_id}/pricing/quote",
    response_model=CustomerQuoteResult,
)
async def customer_pricing_quote(
    customer_id: UUID,
    req: QuoteRequest,
    db: AsyncSession = Depends(get_db),
) -> CustomerQuoteResult:
    try:
        return await _customer_quote(customer_id, req, db)
    except BoundsError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except MissingPricingDataError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
```

In `backend/main.py`, update the import and registration:

```python
from modules.pricing.routes import router as pricing_router, customer_router as pricing_customer_router
```

```python
app.include_router(pricing_router)
app.include_router(pricing_customer_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && pytest tests/test_pricing_customer.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/pricing/routes.py backend/main.py backend/tests/test_pricing_customer.py
git commit -m "feat(pricing): POST /api/customers/{id}/pricing/quote with markup"
```

---

### Task 8: Storefront override end-to-end test

**Files:**
- Test: `backend/tests/test_pricing_customer.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_pricing_customer.py`:

```python
@pytest.mark.asyncio
async def test_storefront_override_replaces_unit_price(db, seed_supplier):
    """A fixed_unit_price override replaces both base price and markup."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import (
        ApparelDetailsIngest,
        PriceTier,
        ProductIngest,
        VariantIngest,
    )
    from modules.catalog.models import Product, ProductVariant
    from modules.customers.models import Customer
    from modules.markup.models import MarkupRule
    from modules.ops_config.models import ProductStorefrontConfig
    from modules.pricing.customer_quote import customer_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select

    payload = ProductIngest(
        supplier_sku="OVR-1",
        product_name="storefront override",
        product_type="apparel",
        pricing_method="tiered_variants",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="OVR-V1",
                prices=[PriceTier(price=Decimal("12.50"))],
            ),
        ],
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        customer = Customer(
            name="Override Co",
            ops_base_url="https://test3.ops.com",
            ops_token_url="https://test3.ops.com/token",
            ops_client_id="x",
            ops_auth_config={"client_secret": "x"},
        )
        s.add(customer)
        await s.flush()
        s.add(MarkupRule(
            customer_id=customer.id,
            scope="all",
            markup_pct=Decimal("25.00"),
            rounding="none",
            priority=0,
        ))
        s.add(ProductStorefrontConfig(
            product_id=product.id,
            customer_id=customer.id,
            ops_category_id="999",
            option_mappings={},
            pricing_overrides={"fixed_unit_price": "20.00"},
        ))
        await s.commit()
        pid = product.id
        vid = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()
        cust_id = customer.id

    async with async_session() as s:
        result = await customer_quote(
            cust_id, QuoteRequest(product_id=pid, variant_id=vid, qty=2), s
        )
        assert result.base_unit_price == Decimal("12.50")
        assert result.unit_price == Decimal("20.00")
        assert result.total == Decimal("40.00")
        assert result.storefront_override_applied is True

        await s.execute(delete(Product).where(Product.id == pid))
        await s.execute(delete(Customer).where(Customer.id == cust_id))
        await s.commit()
```

- [ ] **Step 2: Run test**

Run: `cd backend && pytest tests/test_pricing_customer.py::test_storefront_override_replaces_unit_price -v`
Expected: PASS — `_apply_storefront_override` already implemented in Task 6.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_pricing_customer.py
git commit -m "test(pricing): storefront override end-to-end"
```

---

### Task 9: Decimal precision regression suite

**Files:**
- Test: `backend/tests/test_pricing_apparel.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_pricing_apparel.py`:

```python
@pytest.mark.asyncio
async def test_apparel_quote_quantizes_to_two_decimals(db, seed_supplier):
    """Tier prices that store sub-cent values still round to two decimals on the wire."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import (
        ApparelDetailsIngest,
        PriceTier,
        ProductIngest,
        VariantIngest,
    )
    from modules.catalog.models import Product, ProductVariant
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select, delete

    payload = ProductIngest(
        supplier_sku="QUANT-1",
        product_name="quant",
        product_type="apparel",
        pricing_method="tiered_variants",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="QV1",
                base_price=Decimal("3.337"),
                prices=[PriceTier(price=Decimal("3.337"))],
            ),
        ],
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = product.id
        vid = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()

    async with async_session() as s:
        result = await resolve_quote(
            QuoteRequest(product_id=pid, variant_id=vid, qty=3), s
        )
        # 3.337 -> 3.34, * 3 = 10.02 (no rebuilding from sub-cent)
        assert result.unit_price == Decimal("3.34")
        assert result.total == Decimal("10.02")
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()


@pytest.mark.asyncio
async def test_apparel_resolver_currency_passthrough(db, seed_supplier):
    """USD is the only currency, but the response always includes it."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import (
        ApparelDetailsIngest,
        PriceTier,
        ProductIngest,
        VariantIngest,
    )
    from modules.catalog.models import Product, ProductVariant
    from modules.pricing.resolvers import resolve_quote
    from modules.pricing.schemas import QuoteRequest
    from database import async_session
    from sqlalchemy import select, delete

    payload = ProductIngest(
        supplier_sku="CUR-1",
        product_name="cur",
        product_type="apparel",
        pricing_method="tiered_variants",
        apparel_details=ApparelDetailsIngest(),
        variants=[
            VariantIngest(
                part_id="CURV1",
                prices=[PriceTier(price=Decimal("9.99"))],
            ),
        ],
    )
    async with async_session() as s:
        product = await persist_product(payload, seed_supplier, s)
        await s.commit()
        pid = product.id
        vid = (await s.execute(
            select(ProductVariant.id).where(ProductVariant.product_id == pid)
        )).scalar_one()

    async with async_session() as s:
        result = await resolve_quote(
            QuoteRequest(product_id=pid, variant_id=vid, qty=1), s
        )
        assert result.currency == "USD"
        await s.execute(delete(Product).where(Product.id == pid))
        await s.commit()
```

- [ ] **Step 2: Run tests**

Run: `cd backend && pytest tests/test_pricing_apparel.py::test_apparel_quote_quantizes_to_two_decimals tests/test_pricing_apparel.py::test_apparel_resolver_currency_passthrough -v`
Expected: 2 PASS.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_pricing_apparel.py
git commit -m "test(pricing): decimal quantization + currency regression"
```

---

### Task 10: Full pricing suite + regression sweep

**Files:**
- Test: all of `backend/tests/test_pricing_*.py`

- [ ] **Step 1: Run the full pricing suite**

Run: `cd backend && pytest tests/test_pricing_apparel.py tests/test_pricing_print.py tests/test_pricing_customer.py -v`
Expected: every test PASS.

- [ ] **Step 2: Run the full backend suite to confirm no regression**

Run: `cd backend && pytest tests/ -v`
Expected: all PASS. Anything red that pre-existed gets fixed in a separate commit, not here.

- [ ] **Step 3: Smoke-check `/docs`**

Run the dev server (`uvicorn main:app --reload --port 8000`) and visit `http://127.0.0.1:8000/docs`. Confirm:

- `POST /api/pricing/quote` is listed under tag `pricing`
- `POST /api/customers/{customer_id}/pricing/quote` is listed under tag `pricing`
- request schema shows `product_id` (UUID), `variant_id?`, `width?`, `height?`, `qty>0`, `selected_attribute_ids[]`
- response schema shows `unit_price`, `total`, `currency`, `breakdown` (oneOf apparel/print)

If anything is missing, the OpenAPI generation likely choked on a Pydantic union. Add a discriminator or make `breakdown` typed `dict` as a last resort and re-test.

- [ ] **Step 4: Commit**

```bash
# nothing changed in source unless step 3 found an issue; still tag the milestone
git commit --allow-empty -m "ci(pricing): phase 4 endpoints green; openapi schema ok"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Implemented in |
|--------------|----------------|
| §9 Pricing API endpoint shape `POST /api/pricing/quote` | Tasks 1, 2, 5 |
| §9 apparel resolver: variant_prices lookup + base_price fallback | Task 3 |
| §9 print resolver: base × area × multipliers + setup_cost | Task 4 |
| §9 markup-aware `POST /api/customers/{id}/pricing/quote` | Tasks 6, 7 |
| §11.3 apparel tier match (qty=1 vs qty=144 boundaries) | Task 3 |
| §11.3 apparel fallback breakdown notes "fallback" | Task 3 |
| §11.3 print formula evaluated with full breakdown | Task 4 |
| §11.3 print zero/out-of-bounds dimensions → 400 | Tasks 4, 5 |
| §11.3 markup endpoint applies customer markup | Tasks 6, 7 |
| §12 Phase 4 rollout (anonymous + customer-aware routes) | Tasks 5, 7 |

**2. Spec gaps surfaced during planning** (raised, not blocking):

- Spec §9 referred to `customers.markup_config` but the live model is `markup_rules` table. Plan uses the existing `markup_rules` + `modules/markup/engine.resolve_rule`/`apply_markup` instead — capability is equivalent, naming is just stale.
- Spec §9 print breakdown example showed `"qty_break": {"qty": 50, "discount": "0.95"}` as a single object; the plan treats `qty_break` as a list of `{qty_min, discount}` rows so multiple breaks compose correctly.

**3. Placeholder scan:** None remaining. Every step has explicit code or commands.

**4. Type consistency:**
- `QuoteRequest`, `QuoteResult`, `CustomerQuoteResult`, `ApparelBreakdown`, `PrintBreakdown`, `TierMatch`, `OptionMultiplierTrace` — defined in Task 1, used unchanged across Tasks 3–9.
- `_to_cents` — defined in Task 2 (`resolvers.py`), reused in `customer_quote.py` Task 6.
- `BoundsError`, `MissingPricingDataError` — defined Task 1, raised Tasks 3/4/6, mapped to HTTP in Tasks 5/7.
- `resolve_quote` — defined Task 2, imported by Task 6 (`customer_quote.py`) and Task 5 (`routes.py`).
- Resolvers split across `resolvers_apparel.py` (Task 3) and `resolvers_print.py` (Task 4); `resolve_quote` in `resolvers.py` imports them lazily to avoid circular imports.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-29-phase4-pricing-api.md`. Two execution options:

**1. Subagent-Driven (recommended)** — fresh subagent per task, review between, fast iteration via `superpowers:subagent-driven-development`

**2. Inline Execution** — batch execution with checkpoints via `superpowers:executing-plans`

Which approach?
