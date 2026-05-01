# Polymorphic PDP — Runbook

Phase 5 shipped on 2026-05-01. This document is the canonical reference for the
polymorphic Product Detail Page architecture.

---

## Architecture overview

```
/storefront/vg/product/[product_id]
  └── page.tsx                   fetches /api/products/:id
        └── ProductDetailPanel   dispatcher
              ├── product_type === "print"   → PrintDetailPanel
              └── else                       → ApparelDetailPanel
```

### Apparel flow (`pricing_method: "tiered_variants"`)

```
ApparelDetailPanel
  ├── VariantPicker          colour × size matrix; derives selectedVariant
  ├── PriceBlock             unit price from selected tier at qty=1
  ├── PriceTierTable         qty bands (UNBOUNDED=2 147 483 647 → "X+")
  └── ApparelMeta            gender, fabric, FOB, on-demand badge
```

### Print flow (`pricing_method: "formula"`)

```
PrintDetailPanel
  ├── DimensionInput         width × height with min/max validation
  ├── qty input              integer ≥ 1
  ├── OptionGroupedForm      options grouped by section (Material / Production / …)
  └── LivePriceQuote         debounced quote via useDebouncedQuote
```

---

## Key files

| Path | Purpose |
|------|---------|
| `src/lib/types.ts` | Canonical TypeScript types for all product shapes |
| `src/lib/option-groups.ts` | Groups `ProductOption[]` into named sections |
| `src/lib/use-debounced-quote.ts` | 250 ms debounced `/api/pricing/quote` POST |
| `src/components/storefront/product-detail-panel.tsx` | Dispatcher component |
| `src/components/storefront/apparel-detail-panel.tsx` | Apparel PDP |
| `src/components/storefront/print-detail-panel.tsx` | Print PDP |
| `src/components/storefront/dimension-input.tsx` | Width/height inputs with bounds |
| `src/components/storefront/option-grouped-form.tsx` | Print option sections |
| `src/components/storefront/live-price-quote.tsx` | Live quote display |
| `src/components/storefront/price-tier-table.tsx` | Qty band table |
| `src/components/storefront/product-type-filter.tsx` | Catalog type pills |

---

## Quote API contract

```
POST /api/pricing/quote
Content-Type: application/json

{
  "product_id": "uuid",
  "variant_id": "uuid | null",     // apparel only
  "width": 24,                      // print only (inches)
  "height": 36,                     // print only (inches)
  "qty": 50,
  "selected_attribute_ids": ["a-matte"]  // print options
}

200 OK
{
  "unit_price": "12.50",
  "total":      "625.00",
  "currency":   "USD",
  "breakdown":  { "base": "8.00", "area_multiplier": "6.00", "setup_cost": "10.00" }
}
```

All money values are `string` (Decimal-safe). Never use `parseFloat` on price fields
when displaying them — pass the string directly to the UI.

---

## useDebouncedQuote

```ts
const { quote, loading, error } = useDebouncedQuote({
  enabled: width > 0 && height > 0,
  body: { product_id, width, height, qty, selected_attribute_ids },
  debounceMs: 250,          // default; override in tests
});
```

**Stale-request cancellation:** an internal `requestId` ref increments on every
effect run. The async callback only commits state when its captured id still equals
the ref — stale responses from slow networks are silently discarded.

---

## Option sections

`groupOptionsBySection(options)` maps each `ProductOption` to a named section:

| Section | Matched `option_key` prefixes / values |
|---------|----------------------------------------|
| Material | substrate, material, media, laminate, film, coating, finish |
| Production | quantity, turnaround, production, rush, shipping |
| Cutting | cut, contour, die |
| Design | template, proof, bleed, fold |
| Other | everything else |

Options with `options_type === "admin_only"` or `"textmp"` are hidden from the
storefront. Sections with zero visible options are not rendered.

---

## ProductTypeFilter (catalog page)

The `<ProductTypeFilter>` renders a pill row above the product grid:

- **All** pill always present; active when `value === null`
- One pill per distinct `product_type` present in the loaded product list
- Clicking an active pill clears the filter (toggles back to `null`)

The available types are derived client-side from the loaded `products` array, so
no additional API call is needed.

---

## Running the test suite

```bash
# Unit + component tests (Vitest + jsdom)
cd frontend && npm test
# Expected: 21 tests across 9 files — all pass

# E2E tests (Playwright, Chromium)
cd frontend && npm run test:e2e
# Expected: 3 tests — all pass (no backend required; routes are mocked)

# Type checking
cd frontend && npx tsc --noEmit
# Expected: silent (exit 0)

# Lint
cd frontend && npm run lint
# Expected: warnings only (pre-existing); zero errors
```

### E2E test fixtures

| Fixture | Used by |
|---------|---------|
| `e2e/fixtures/apparel-product.json` | `apparel-pdp.spec.ts` |
| `e2e/fixtures/print-product.json` | `print-pdp.spec.ts` |
| `e2e/fixtures/quote-response.json` | `print-pdp.spec.ts` |

All e2e specs mock `**/api/**` at the browser network layer via `page.route()`.
The Playwright `webServer` config starts `npm run dev` on port 3000 and reuses
an already-running server (`reuseExistingServer: true`).

---

## Adding a new product type

1. Add the type literal to `ProductType` in `src/lib/types.ts`.
2. Create `src/components/storefront/<type>-detail-panel.tsx`.
3. Add a branch to `ProductDetailPanel` in `product-detail-panel.tsx`.
4. Add an e2e fixture under `e2e/fixtures/` and a spec in `e2e/`.
5. Update `catalog-filter.spec.ts` fixture list if the catalog should show it.

---

## Known limitations / future work

- `print-detail-panel` qty input is a plain `<input type="number">`; replace with
  a validated `<QuantityInput>` component when one is standardised.
- `ApparelDetailPanel` does not yet call `/api/pricing/quote`; it reads prices
  directly from variant tier data. A live-quote path may be added in Phase 6 for
  decoration cost overlays.
- `ProductTypeFilter` pills are derived from loaded products only — if the catalog
  is paginated and a type only appears on later pages, its pill won't render until
  those pages load.
