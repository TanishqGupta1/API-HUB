# Phase 4 — Pricing API: Task Categories

> Source plan: `docs/superpowers/plans/2026-04-29-phase4-pricing-api.md`
> Date: 2026-04-30
> Status: All 10 tasks complete — 22/22 tests passing

---

## Category Overview

| Category | Tasks |
|----------|-------|
| Backend — Module / Business Logic | 1, 2, 3, 4, 6 |
| Backend — API Routes | 5, 7 |
| Backend — Tests | 8, 9, 10 |
| Database | (no new tables — uses existing models) |
| Frontend | (out of scope — Phase 5) |

---

## Backend — Module / Business Logic

These tasks live in `backend/modules/pricing/` and contain the pure logic with no HTTP layer.

### Task 1: Module Skeleton + Pydantic Schemas
**Files:**
- `backend/modules/pricing/__init__.py`
- `backend/modules/pricing/schemas.py`
- `backend/modules/pricing/errors.py`

**What it does:**
- Defines the shared request model `QuoteRequest` (product_id, variant_id, width, height, qty, selected_attribute_ids)
- Defines response models: `QuoteResult`, `CustomerQuoteResult`, `ApparelBreakdown`, `PrintBreakdown`, `TierMatch`, `OptionMultiplierTrace`
- Defines error hierarchy: `PricingError` → `BoundsError`, `MissingPricingDataError`

---

### Task 2: BaseResolver Interface + Dispatch
**Files:**
- `backend/modules/pricing/resolvers.py`

**What it does:**
- Defines `BaseResolver` protocol (all resolvers implement `async resolve(req, product, db)`)
- `resolve_quote(req, db)` — loads the product, picks the right resolver based on `product.pricing_method`, calls it
- `_to_cents(value)` — shared Decimal rounding helper (ROUND_HALF_UP to 2dp)
- Dispatches to `TieredVariantResolver` for `pricing_method="tiered_variants"`, `FormulaResolver` for `"formula"`

---

### Task 3: TieredVariantResolver (Apparel)
**Files:**
- `backend/modules/pricing/resolvers_apparel.py`

**What it does:**
- Looks up `variant_prices` rows for the given variant + qty band
- Priority order when multiple tiers match: Net > Sale > MSRP > Case > alphabetical
- Falls back to `variant.base_price` if no tier rows exist (`breakdown.fallback = True`)
- Raises `MissingPricingDataError` if no variant_id supplied or variant not found

---

### Task 4: FormulaResolver (Print)
**Files:**
- `backend/modules/pricing/resolvers_print.py`

**What it does:**
- Formula: `unit = base × (width × height × area_factor) × Π(option multipliers)`
- Validates width/height are within `print_details.width_min/max` / `height_min/max` — raises `BoundsError` if not
- Loads `selected_attribute_ids` → joins `ProductOptionAttribute` → applies `multiplier` and `setup_cost`
- Optional `qty_break` discounts in the formula JSONB
- Raises `MissingPricingDataError` if `print_details.formula` is null

---

### Task 6: Customer-Aware Quote (Markup Wrapper)
**Files:**
- `backend/modules/pricing/customer_quote.py`

**What it does:**
- Calls `resolve_quote` first to get the base price
- Fetches `markup_rules` for the customer, calls `resolve_rule` + `apply_markup` from the existing markup engine
- Applies `product_storefront_configs.pricing_overrides` last:
  - `fixed_unit_price` — replaces the marked-up price outright
  - `extra_markup_pct` — stacks on top of the marked-up price
  - `rounding` — `nearest_99` or `nearest_dollar`
- Returns `CustomerQuoteResult` with `base_unit_price`, `markup_pct`, `rounding`, `storefront_override_applied`

---

## Backend — API Routes

These tasks wire the business logic to HTTP endpoints via FastAPI.

### Task 5: Anonymous Quote Endpoint
**Files:**
- `backend/modules/pricing/routes.py` (created)
- `backend/main.py` (modified — imports + registers router)

**Endpoint:** `POST /api/pricing/quote`

**What it does:**
- Accepts `QuoteRequest` body
- Calls `resolve_quote`
- Maps `BoundsError` → 400, `MissingPricingDataError` → 404
- Returns `QuoteResult` (unit_price, total, currency, breakdown)

---

### Task 7: Customer-Aware Quote Endpoint
**Files:**
- `backend/modules/pricing/routes.py` (modified)
- `backend/main.py` (modified — registers second router)

**Endpoint:** `POST /api/customers/{customer_id}/pricing/quote`

**What it does:**
- Same as Task 5 but wraps with customer markup + storefront overrides
- Calls `customer_quote(customer_id, req, db)`
- Returns `CustomerQuoteResult` (adds base_unit_price, markup_pct, rounding, storefront_override_applied)

---

## Backend — Tests

All tests use pytest-asyncio + a real PostgreSQL database (no mocks). Data is seeded via `persist_product` and cleaned up within each test.

### Task 8: Storefront Override E2E Test
**File:** `backend/tests/test_pricing_customer.py`

**Covers:**
- `fixed_unit_price` override replaces both base price and markup
- Verifies `storefront_override_applied = True` in the response

---

### Task 9: Decimal Precision Regression Suite
**File:** `backend/tests/test_pricing_apparel.py`

**Covers:**
- Sub-cent tier prices (e.g. `3.337`) round to 2dp on the wire (`3.34`)
- `total` is computed from the already-rounded `unit_price` (no accumulated float error)
- `currency = "USD"` always present

---

### Task 10: Full Suite + Smoke Check
**Files:** All `backend/tests/test_pricing_*.py`

**Covers:**
- Runs all 22 pricing tests together
- Runs full backend test suite to confirm no regressions
- Smoke-checks `/docs` OpenAPI — both pricing routes listed, schema correct

---

## Database

**No new migrations in Phase 4.** The pricing engine reads from tables already created in Phase 1:

| Table | Used By |
|-------|---------|
| `products` | All resolvers — loads `pricing_method`, `supplier_sku`, `category` |
| `product_variants` | `TieredVariantResolver` — loads `base_price` |
| `variant_prices` | `TieredVariantResolver` — tier lookup (group_name, qty_min, qty_max, price) |
| `print_details` | `FormulaResolver` — loads `formula`, `width_min/max`, `height_min/max` |
| `product_options` | `FormulaResolver` — joins to attributes for multipliers |
| `product_option_attributes` | `FormulaResolver` — `multiplier`, `setup_cost` |
| `markup_rules` | `customer_quote` — resolves markup % by scope |
| `product_storefront_configs` | `customer_quote` — applies `pricing_overrides` JSONB |
| `customers` | `customer_quote` — validates customer exists |

---

## Frontend

**Out of scope for Phase 4.** Frontend price preview UI is Phase 5.

---

## File Map Summary

```
backend/
├── modules/
│   └── pricing/
│       ├── __init__.py          Task 1 — module marker
│       ├── schemas.py           Task 1 — QuoteRequest, QuoteResult, breakdowns
│       ├── errors.py            Task 1 — PricingError, BoundsError, MissingPricingDataError
│       ├── resolvers.py         Task 2 — BaseResolver protocol, resolve_quote dispatch, _to_cents
│       ├── resolvers_apparel.py Task 3 — TieredVariantResolver
│       ├── resolvers_print.py   Task 4 — FormulaResolver
│       ├── routes.py            Tasks 5, 7 — FastAPI endpoints
│       └── customer_quote.py    Task 6 — markup + storefront override wrapper
├── main.py                      Tasks 5, 7 — router registration
└── tests/
    ├── test_pricing_apparel.py  Tasks 1, 2, 3, 5, 9
    ├── test_pricing_print.py    Tasks 4, 5
    ├── test_pricing_customer.py Tasks 6, 7, 8
    └── test_pricing_routes.py   Tasks 5, 7
```
