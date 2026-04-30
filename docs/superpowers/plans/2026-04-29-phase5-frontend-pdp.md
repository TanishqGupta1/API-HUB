# Phase 5 Frontend PDP Implementation Plan

> **STATUS (2026-04-30): 🟢 UNBLOCKED — ready to execute after Phase 4.** Backend polymorphic model from Phase 1 is merged. `apparel_details`, `print_details`, `variant_prices`, `product_sizes` exist and accessible via `ProductRead`. Phase 4 pricing API is the remaining backend dependency. Once Phase 4 ships `/api/pricing/quote`, this plan can begin.
>
> **Parallel-safe with Phase 6:** This plan touches storefront PDP routes (`frontend/src/app/storefront/...`). Phase 6 catalog UI touches admin shell + catalog list. No file overlap. Can ship in parallel.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing storefront PDP at `/storefront/vg/product/[product_id]` so it renders apparel and print products from one route, switching the body by `product.product_type`. Apparel keeps the existing `<VariantPicker>` + `<PriceBlock>` flow but reads variant-tier prices from `variant_prices`. Print products get a new `<DimensionInput>` + `<OptionGroupedForm>` + `<LivePriceQuote>` configurator that calls `/api/pricing/quote` for live prices. The catalog list page gets a `product_type` filter pill driven from list endpoint metadata.

**Architecture:** Existing route `frontend/src/app/storefront/vg/product/[product_id]/page.tsx` stays as the entry point. Extract type dispatch into a new client component `<ProductDetailPanel>` that renders the apparel or print body. New hook `useDebouncedQuote` posts the print configurator state to `/api/pricing/quote` after a 250 ms debounce and surfaces the breakdown. Extend `lib/types.ts` with `apparel_details`, `print_details`, `variant_prices`, `product_sizes`, `pricing_method`, and `PriceQuote` to mirror Phase 1/4 backend schemas. The existing `<PDPLayout>`, `<ImageGallery>`, `<DescriptionHtml>`, `<RelatedProducts>` shells are reused unchanged.

**Tech Stack:** Next.js 15 App Router, React 19, TypeScript, shadcn/ui (`@/components/ui/*`), Tailwind 3, Blueprint design system tokens (Outfit + Fira Code, paper `#f2f0ed`, blueprint blue `#1e4d92`), `@/lib/api` fetch wrapper. Vitest + Testing Library for component tests, Playwright for e2e. Both test runners are added by Task 1 (frontend currently has zero test config).

**Spec:** `docs/superpowers/specs/2026-04-29-multi-supplier-product-model-design.md` — uses §8 Frontend, §9 Pricing API contract, §11.4 Playwright tests, §12 Phase 5 rollout.

**Out of scope (explicitly):** Backend changes (Phase 1-4 must already be deployed for this plan to land), cart / checkout, customer-aware pricing UI (`/api/customers/{id}/pricing/quote`), native mobile apps, template-product PDP, admin-side product detail page (`/products/[id]` under `(admin)/`).

**Reuses existing code:**
- `frontend/src/app/storefront/vg/product/[product_id]/page.tsx` — kept; its body is reorganized to delegate to `<ProductDetailPanel>`.
- `frontend/src/components/storefront/pdp-layout.tsx` — unchanged.
- `frontend/src/components/storefront/image-gallery.tsx` — unchanged.
- `frontend/src/components/storefront/variant-picker.tsx` — unchanged; absorbed into the apparel panel via composition. Color hex from `pms_color` is added in Task 7 by a thin override prop, NOT a rewrite.
- `frontend/src/components/storefront/price-block.tsx` — apparel keeps using it; the new `<PriceTierTable>` sits alongside.
- `frontend/src/components/storefront/product-options.tsx` — apparel still uses this for legacy options. Print uses the new `<OptionGroupedForm>` instead.
- `frontend/src/components/storefront/related-products.tsx` — unchanged.
- `frontend/src/lib/api.ts` — unchanged; reused.

**New components introduced:**
- `<ProductDetailPanel>` — type dispatch
- `<ApparelDetailPanel>` — apparel body
- `<PrintDetailPanel>` — print body
- `<DimensionInput>` — width × height input bounded by `print_details`
- `<OptionGroupedForm>` — print options grouped by section, rendered by `options_type`
- `<LivePriceQuote>` — debounced quote display with breakdown
- `<PriceTierTable>` — apparel `variant_prices` summary
- `<ProductTypeFilter>` — catalog list filter pill

---

## File Structure

### Files to create
- `frontend/src/components/storefront/product-detail-panel.tsx` — type dispatcher
- `frontend/src/components/storefront/apparel-detail-panel.tsx` — apparel body wrapper
- `frontend/src/components/storefront/print-detail-panel.tsx` — print body wrapper
- `frontend/src/components/storefront/dimension-input.tsx` — width × height input
- `frontend/src/components/storefront/option-grouped-form.tsx` — print options grouped form
- `frontend/src/components/storefront/live-price-quote.tsx` — debounced quote display
- `frontend/src/components/storefront/price-tier-table.tsx` — apparel tier table
- `frontend/src/components/storefront/product-type-filter.tsx` — list page filter pill
- `frontend/src/lib/use-debounced-quote.ts` — `/api/pricing/quote` hook
- `frontend/src/lib/option-groups.ts` — option-key → section grouping (Material/Production/Cutting/Design)
- `frontend/src/components/storefront/__tests__/product-detail-panel.test.tsx`
- `frontend/src/components/storefront/__tests__/dimension-input.test.tsx`
- `frontend/src/components/storefront/__tests__/option-grouped-form.test.tsx`
- `frontend/src/components/storefront/__tests__/live-price-quote.test.tsx`
- `frontend/src/components/storefront/__tests__/price-tier-table.test.tsx`
- `frontend/src/components/storefront/__tests__/product-type-filter.test.tsx`
- `frontend/src/lib/__tests__/option-groups.test.ts`
- `frontend/src/lib/__tests__/use-debounced-quote.test.ts`
- `frontend/vitest.config.ts` — Vitest jsdom setup
- `frontend/vitest.setup.ts` — `@testing-library/jest-dom` matchers
- `frontend/playwright.config.ts` — Playwright config
- `frontend/e2e/apparel-pdp.spec.ts` — Playwright apparel PDP e2e
- `frontend/e2e/print-pdp.spec.ts` — Playwright print PDP e2e
- `frontend/e2e/catalog-filter.spec.ts` — Playwright catalog filter e2e
- `frontend/e2e/fixtures/apparel-product.json` — captured apparel response
- `frontend/e2e/fixtures/print-product.json` — captured print response
- `frontend/e2e/fixtures/quote-response.json` — captured `/api/pricing/quote` response

### Files to modify
- `frontend/src/lib/types.ts` — extend with polymorphic types
- `frontend/src/app/storefront/vg/product/[product_id]/page.tsx` — delegate body to `<ProductDetailPanel>`
- `frontend/src/app/storefront/vg/page.tsx` (catalog list) — wire `<ProductTypeFilter>`
- `frontend/src/app/storefront/vg/category/[category_id]/page.tsx` (category list) — wire `<ProductTypeFilter>`
- `frontend/package.json` — add Vitest, Testing Library, Playwright, jsdom
- `frontend/.gitignore` — add `playwright-report/` and `test-results/`

### Files NOT touched
- `frontend/src/app/(admin)/**` — admin product page out of scope.
- Any backend file. This plan assumes Phase 1, 2, 3, 4 backends are deployed.
- `frontend/src/components/storefront/variant-picker.tsx` is read by the apparel panel but **not edited** in this plan; it already accepts a flat list of variants and emits a selection.

---

## Task Breakdown

### Task 1: Add Vitest + Playwright dev dependencies and base config

**Files:**
- Modify: `frontend/package.json`
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/playwright.config.ts`
- Modify: `frontend/.gitignore`

- [ ] **Step 1: Install Vitest + Testing Library + jsdom + Playwright**

```bash
cd frontend && npm install --save-dev \
  vitest@^1.6.0 \
  @vitest/ui@^1.6.0 \
  @vitejs/plugin-react@^4.3.0 \
  @testing-library/react@^16.0.0 \
  @testing-library/jest-dom@^6.4.6 \
  @testing-library/user-event@^14.5.2 \
  jsdom@^24.1.0 \
  @playwright/test@^1.45.0
cd frontend && npx playwright install --with-deps chromium
```

- [ ] **Step 2: Add npm scripts**

In `frontend/package.json` `scripts`, add:

```json
"test": "vitest run",
"test:watch": "vitest",
"test:e2e": "playwright test"
```

- [ ] **Step 3: Create `frontend/vitest.config.ts`**

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { fileURLToPath } from "node:url";
import path from "node:path";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.{test,spec}.{ts,tsx}"],
    exclude: ["e2e/**", "node_modules/**"],
  },
  resolve: {
    alias: { "@": path.resolve(__dirname, "src") },
  },
});
```

- [ ] **Step 4: Create `frontend/vitest.setup.ts`**

```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 5: Create `frontend/playwright.config.ts`**

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: true,
  retries: 0,
  reporter: [["html", { open: "never" }], ["list"]],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3000",
    trace: "retain-on-failure",
    actionTimeout: 5_000,
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
```

- [ ] **Step 6: Add Playwright artifacts to `frontend/.gitignore`**

Append two lines:

```
playwright-report/
test-results/
```

- [ ] **Step 7: Verify the runners boot**

```bash
cd frontend && npm run test -- --reporter=verbose
cd frontend && npm run test:e2e -- --list
```

Expected: `npm run test` exits 0 with "no tests found"; `test:e2e -- --list` prints zero tests but does not error.

- [ ] **Step 8: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/vitest.config.ts frontend/vitest.setup.ts frontend/playwright.config.ts frontend/.gitignore
git commit -m "chore(frontend): add vitest + playwright test runners"
```

---

### Task 2: Extend TypeScript types for polymorphic products and price quote

**Files:**
- Modify: `frontend/src/lib/types.ts`

- [ ] **Step 1: Write the failing test**

Create `frontend/src/lib/__tests__/types.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { Product, PriceQuote } from "@/lib/types";

describe("polymorphic Product types", () => {
  it("apparel product carries apparel_details + variant_prices", () => {
    const apparel: Product = {
      id: "p1",
      supplier_id: "s1",
      supplier_name: "SanMar",
      supplier_sku: "PC61",
      product_name: "Polo",
      brand: "Mercer+Mettle",
      category: null,
      category_id: null,
      description: null,
      product_type: "apparel",
      pricing_method: "tiered_variants",
      image_url: null,
      ops_product_id: null,
      external_catalogue: null,
      last_synced: null,
      archived_at: null,
      variants: [
        {
          id: "v1",
          color: "Deep Black",
          size: "S",
          sku: "PC61-DB-S",
          base_price: 24.98,
          inventory: null,
          warehouse: null,
          part_id: "1878771",
          gtin: null,
          flags: { pms_color: "BLACK C", standard_color: "Deep Black" },
          prices: [
            { group_name: "MSRP", qty_min: 1, qty_max: 11, price: "24.98", currency: "USD" },
            { group_name: "MSRP", qty_min: 12, qty_max: 2147483647, price: "19.98", currency: "USD" },
          ],
        },
      ],
      images: [],
      options: [],
      apparel_details: {
        ps_part_id: "1878771",
        apparel_style: "Mens",
        is_closeout: false,
        is_hazmat: null,
        is_caution: false,
        caution_comment: null,
        is_on_demand: null,
        fabric_specs: { weight_oz: 8.1 },
        fob_points: null,
        keywords: null,
      },
      print_details: null,
      sizes: [],
    };
    expect(apparel.apparel_details?.apparel_style).toBe("Mens");
    expect(apparel.variants[0].prices[0].price).toBe("24.98");
  });

  it("PriceQuote breakdown is freeform JSON", () => {
    const quote: PriceQuote = {
      unit_price: "12.50",
      total: "625.00",
      currency: "USD",
      breakdown: { base: "8.00", area_multiplier: "6.00", setup_cost: "10.00" },
    };
    expect(quote.total).toBe("625.00");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm run test -- src/lib/__tests__/types.test.ts
```

Expected: FAIL — type errors / missing exports for `apparel_details`, `print_details`, `pricing_method`, `prices`, `sizes`, `PriceQuote`.

- [ ] **Step 3: Extend `frontend/src/lib/types.ts`**

In the `/* ─── Product Catalog ─── */` section, replace `Variant`, `Product`, and `ProductListItem`, and add the new shapes:

```ts
export interface VariantPriceTier {
  group_name: string;
  qty_min: number;
  qty_max: number;
  price: string;        // backend returns Decimal as string for precision
  currency: string;
  effective_from?: string | null;
  effective_to?: string | null;
}

export interface Variant {
  id: string;
  color: string | null;
  size: string | null;
  sku: string | null;
  base_price: number | null;
  inventory: number | null;
  warehouse: string | null;
  part_id: string | null;
  gtin: string | null;
  flags: Record<string, unknown> | null;   // pms_color, standard_color, label_size, weight_oz
  prices: VariantPriceTier[];
}

export interface ApparelDetails {
  ps_part_id: string | null;
  apparel_style: string | null;
  is_closeout: boolean;
  is_hazmat: boolean | null;
  is_caution: boolean;
  caution_comment: string | null;
  is_on_demand: boolean | null;
  fabric_specs: Record<string, unknown> | null;
  fob_points: Array<Record<string, unknown>> | null;
  keywords: string[] | null;
}

export interface PrintDetails {
  ops_product_id_int: number | null;
  default_category_id: number | null;
  external_catalogue: number | null;
  width_min: string | null;
  width_max: string | null;
  height_min: string | null;
  height_max: string | null;
  formula: Record<string, unknown> | null;
  size_template_id: number | null;
}

export interface ProductSize {
  id: string;
  ops_size_id: number | null;
  size_title: string;
  size_width: string;
  size_height: string;
  width_min: string | null;
  width_max: string | null;
  height_min: string | null;
  height_max: string | null;
  sort_order: number;
}

export type ProductType = "apparel" | "print" | "template" | "promo";
export type PricingMethod = "tiered_variants" | "formula";

export interface Product {
  id: string;
  supplier_id: string;
  supplier_name: string;
  supplier_sku: string;
  product_name: string;
  brand: string | null;
  category: string | null;
  category_id: string | null;
  description: string | null;
  product_type: ProductType;
  pricing_method: PricingMethod | null;
  image_url: string | null;
  ops_product_id: string | null;
  external_catalogue: number | null;
  last_synced: string | null;
  archived_at: string | null;
  variants: Variant[];
  images: ProductImage[];
  options: ProductOption[];
  apparel_details: ApparelDetails | null;
  print_details: PrintDetails | null;
  sizes: ProductSize[];
}

export interface ProductListItem {
  id: string;
  supplier_id: string;
  supplier_name: string;
  supplier_sku: string;
  product_name: string;
  brand: string | null;
  category_id: string | null;
  product_type: ProductType;
  pricing_method: PricingMethod | null;
  image_url: string | null;
  ops_product_id: string | null;
  external_catalogue: number | null;
  variant_count: number;
  price_min: number | null;
  price_max: number | null;
  total_inventory: number | null;
  archived_at: string | null;
}

/* ─── Pricing Quote ───────────────────────────────────────────────────────── */
export interface PriceQuoteRequest {
  product_id: string;
  variant_id?: string;
  width?: number;
  height?: number;
  qty: number;
  selected_attribute_ids?: string[];
}

export interface PriceQuote {
  unit_price: string;
  total: string;
  currency: string;
  breakdown: Record<string, unknown>;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm run test -- src/lib/__tests__/types.test.ts
```

Expected: PASS.

- [ ] **Step 5: Repair existing call sites that broke from the type change**

Type-check the project:

```bash
cd frontend && npx tsc --noEmit
```

Expected errors are limited to call sites that previously read `Variant` without the new fields. For each error, add the missing fields with safe defaults:

- In any place that constructs a synthetic `Variant`, add `part_id: null, gtin: null, flags: null, prices: []`.
- In any place that reads `Product` and assumes `pricing_method` is absent, treat it as nullable (`product.pricing_method ?? "tiered_variants"`).
- In any place that constructs a `Product` literal, add `pricing_method: "tiered_variants", apparel_details: null, print_details: null, sizes: []`.

Do not touch `<VariantPicker>` — it only reads `id`, `color`, `size` and stays compatible.

- [ ] **Step 6: Re-run typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/__tests__/types.test.ts
git commit -m "feat(frontend): polymorphic product types + PriceQuote"
```

---

### Task 3: Option-key grouping helper

**Files:**
- Create: `frontend/src/lib/option-groups.ts`
- Create: `frontend/src/lib/__tests__/option-groups.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/lib/__tests__/option-groups.test.ts
import { describe, expect, it } from "vitest";
import { groupOptionsBySection } from "@/lib/option-groups";
import type { ProductOption } from "@/lib/types";

const opt = (option_key: string, options_type: string | null = "combo"): ProductOption => ({
  id: `id-${option_key}`,
  option_key,
  title: option_key,
  options_type,
  sort_order: 0,
  master_option_id: null,
  ops_option_id: null,
  required: false,
  attributes: [],
});

describe("groupOptionsBySection", () => {
  it("buckets known OPS keys into Material / Production / Cutting / Design", () => {
    const groups = groupOptionsBySection([
      opt("substrateMaterial"),
      opt("lamMaterial"),
      opt("inkType"),
      opt("prodTime"),
      opt("printSides"),
      opt("printDevice"),
      opt("cutType"),
      opt("kissCutDevice"),
      opt("rcRadius"),
      opt("design"),
      opt("designType"),
      opt("designServices"),
    ]);
    expect(groups.Material.map((o) => o.option_key)).toEqual([
      "substrateMaterial",
      "lamMaterial",
      "inkType",
    ]);
    expect(groups.Production.map((o) => o.option_key)).toEqual([
      "prodTime",
      "printSides",
      "printDevice",
    ]);
    expect(groups.Cutting.map((o) => o.option_key)).toEqual([
      "cutType",
      "kissCutDevice",
      "rcRadius",
    ]);
    expect(groups.Design.map((o) => o.option_key)).toEqual([
      "design",
      "designType",
      "designServices",
    ]);
  });

  it("drops admin_only and textmp options", () => {
    const groups = groupOptionsBySection([
      opt("file_prep", "admin_only"),
      opt("designTime", "textmp"),
      opt("inkFinish", "combo"),
    ]);
    expect(groups.Other.map((o) => o.option_key)).toEqual([]);
    expect(groups.Material.map((o) => o.option_key)).toEqual(["inkFinish"]);
  });

  it("falls back to Other for unknown keys", () => {
    const groups = groupOptionsBySection([opt("specialSign"), opt("zogZog")]);
    expect(groups.Other.map((o) => o.option_key).sort()).toEqual(["specialSign", "zogZog"]);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm run test -- src/lib/__tests__/option-groups.test.ts
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the helper**

Create `frontend/src/lib/option-groups.ts`:

```ts
import type { ProductOption } from "@/lib/types";

export type SectionName = "Material" | "Production" | "Cutting" | "Design" | "Other";

export const SECTION_ORDER: SectionName[] = [
  "Material",
  "Production",
  "Cutting",
  "Design",
  "Other",
];

const HIDDEN_TYPES = new Set(["admin_only", "textmp"]);

const SECTION_KEYS: Record<Exclude<SectionName, "Other">, ReadonlyArray<string>> = {
  Material: [
    "substrateMaterial",
    "substrateType",
    "substrateClass",
    "lamMaterial",
    "inkFinish",
    "inkType",
    "whiteInk",
    "panelType",
    "imageShape",
  ],
  Production: [
    "prodTime",
    "printSides",
    "printDevice",
    "printSurface",
    "printMode_Colorado",
    "printMode_FluidColor",
    "provideProof",
  ],
  Cutting: [
    "cutType",
    "cutting",
    "cutMasking",
    "cutComplexity",
    "kissCutDevice",
    "kissCutDeviceTool",
    "thruCutDevice",
    "thruCutDeviceTool_ThruCut",
    "weeding",
    "lamDevice",
    "rcRadius",
    "specialSign",
  ],
  Design: ["design", "designType", "designServices", "designComm", "designConsult"],
};

export function groupOptionsBySection(
  options: ProductOption[],
): Record<SectionName, ProductOption[]> {
  const out: Record<SectionName, ProductOption[]> = {
    Material: [],
    Production: [],
    Cutting: [],
    Design: [],
    Other: [],
  };
  for (const o of options) {
    if (HIDDEN_TYPES.has(o.options_type ?? "")) continue;
    const section = (Object.keys(SECTION_KEYS) as Array<Exclude<SectionName, "Other">>).find(
      (s) => SECTION_KEYS[s].includes(o.option_key),
    );
    out[section ?? "Other"].push(o);
  }
  return out;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm run test -- src/lib/__tests__/option-groups.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/option-groups.ts frontend/src/lib/__tests__/option-groups.test.ts
git commit -m "feat(frontend): option-key → section grouping helper"
```

---

### Task 4: `useDebouncedQuote` hook

**Files:**
- Create: `frontend/src/lib/use-debounced-quote.ts`
- Create: `frontend/src/lib/__tests__/use-debounced-quote.test.ts`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/lib/__tests__/use-debounced-quote.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useDebouncedQuote } from "@/lib/use-debounced-quote";

describe("useDebouncedQuote", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it("posts request and returns the quote after the debounce window", async () => {
    const fakeFetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        unit_price: "12.50",
        total: "625.00",
        currency: "USD",
        breakdown: { base: "8.00" },
      }),
      headers: new Headers({ "content-type": "application/json" }),
    });
    vi.stubGlobal("fetch", fakeFetch);

    const { result, rerender } = renderHook(
      (props: { qty: number }) =>
        useDebouncedQuote({ enabled: true, body: { product_id: "p1", qty: props.qty }, debounceMs: 250 }),
      { initialProps: { qty: 1 } },
    );

    expect(result.current.quote).toBeNull();
    expect(result.current.loading).toBe(false);

    rerender({ qty: 50 });
    await act(async () => {
      vi.advanceTimersByTime(260);
    });
    await waitFor(() => expect(result.current.quote?.total).toBe("625.00"));
    expect(fakeFetch).toHaveBeenCalledTimes(1);
  });

  it("skips when disabled", async () => {
    const fakeFetch = vi.fn();
    vi.stubGlobal("fetch", fakeFetch);
    renderHook(() =>
      useDebouncedQuote({ enabled: false, body: { product_id: "p1", qty: 1 }, debounceMs: 250 }),
    );
    await act(async () => {
      vi.advanceTimersByTime(500);
    });
    expect(fakeFetch).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm run test -- src/lib/__tests__/use-debounced-quote.test.ts
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the hook**

Create `frontend/src/lib/use-debounced-quote.ts`:

```ts
"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { PriceQuote, PriceQuoteRequest } from "@/lib/types";

interface UseDebouncedQuoteArgs {
  enabled: boolean;
  body: PriceQuoteRequest;
  debounceMs?: number;
}

interface UseDebouncedQuoteResult {
  quote: PriceQuote | null;
  loading: boolean;
  error: string | null;
}

export function useDebouncedQuote(
  { enabled, body, debounceMs = 250 }: UseDebouncedQuoteArgs,
): UseDebouncedQuoteResult {
  const [quote, setQuote] = useState<PriceQuote | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const requestId = useRef(0);
  const serialized = JSON.stringify(body);

  useEffect(() => {
    if (!enabled) {
      setLoading(false);
      return;
    }
    const myId = ++requestId.current;
    const handle = window.setTimeout(async () => {
      setLoading(true);
      setError(null);
      try {
        const result = await api<PriceQuote>("/api/pricing/quote", {
          method: "POST",
          body: serialized,
        });
        if (myId === requestId.current) {
          setQuote(result);
        }
      } catch (err) {
        if (myId === requestId.current) {
          setError(err instanceof Error ? err.message : String(err));
          setQuote(null);
        }
      } finally {
        if (myId === requestId.current) setLoading(false);
      }
    }, debounceMs);

    return () => window.clearTimeout(handle);
  }, [enabled, serialized, debounceMs]);

  return { quote, loading, error };
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm run test -- src/lib/__tests__/use-debounced-quote.test.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/use-debounced-quote.ts frontend/src/lib/__tests__/use-debounced-quote.test.ts
git commit -m "feat(frontend): debounced /api/pricing/quote hook"
```

---

### Task 5: `<DimensionInput>` component

**Files:**
- Create: `frontend/src/components/storefront/dimension-input.tsx`
- Create: `frontend/src/components/storefront/__tests__/dimension-input.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/storefront/__tests__/dimension-input.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DimensionInput } from "@/components/storefront/dimension-input";

describe("DimensionInput", () => {
  it("emits width and height changes", async () => {
    const onChange = vi.fn();
    render(
      <DimensionInput
        width={null}
        height={null}
        widthMin={1}
        widthMax={96}
        heightMin={1}
        heightMax={96}
        onChange={onChange}
      />,
    );
    const w = screen.getByLabelText(/width/i);
    const h = screen.getByLabelText(/height/i);
    await userEvent.type(w, "24");
    await userEvent.type(h, "36");
    expect(onChange).toHaveBeenLastCalledWith({ width: 24, height: 36 });
  });

  it("flags out-of-range values", async () => {
    render(
      <DimensionInput
        width={120}
        height={36}
        widthMin={1}
        widthMax={96}
        heightMin={1}
        heightMax={96}
        onChange={() => {}}
      />,
    );
    expect(screen.getByText(/width must be between/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/dimension-input.test.tsx
```

Expected: FAIL — component missing.

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/components/storefront/dimension-input.tsx
"use client";

import { useEffect, useState } from "react";

export interface DimensionInputValue {
  width: number | null;
  height: number | null;
}

interface Props {
  width: number | null;
  height: number | null;
  widthMin: number | null;
  widthMax: number | null;
  heightMin: number | null;
  heightMax: number | null;
  onChange: (value: DimensionInputValue) => void;
}

export function DimensionInput({
  width,
  height,
  widthMin,
  widthMax,
  heightMin,
  heightMax,
  onChange,
}: Props) {
  const [w, setW] = useState<string>(width === null ? "" : String(width));
  const [h, setH] = useState<string>(height === null ? "" : String(height));

  useEffect(() => {
    const wn = w === "" ? null : Number(w);
    const hn = h === "" ? null : Number(h);
    onChange({ width: Number.isNaN(wn ?? NaN) ? null : wn, height: Number.isNaN(hn ?? NaN) ? null : hn });
  }, [w, h, onChange]);

  const wOut = w !== "" && widthMin != null && widthMax != null
    ? Number(w) < widthMin || Number(w) > widthMax
    : false;
  const hOut = h !== "" && heightMin != null && heightMax != null
    ? Number(h) < heightMin || Number(h) > heightMax
    : false;

  return (
    <div className="grid grid-cols-2 gap-3">
      <label className="flex flex-col gap-1">
        <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
          Width (in)
        </span>
        <input
          aria-label="Width"
          type="number"
          step="0.01"
          min={widthMin ?? undefined}
          max={widthMax ?? undefined}
          value={w}
          onChange={(e) => setW(e.target.value)}
          className="h-9 px-2 text-[13px] border border-[#cfccc8] rounded-md bg-white text-[#1e1e24] focus:outline-none focus:border-[#1e4d92]"
        />
        {wOut ? (
          <span className="text-[10px] text-[#b93232]">
            Width must be between {widthMin} and {widthMax}
          </span>
        ) : null}
      </label>
      <label className="flex flex-col gap-1">
        <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
          Height (in)
        </span>
        <input
          aria-label="Height"
          type="number"
          step="0.01"
          min={heightMin ?? undefined}
          max={heightMax ?? undefined}
          value={h}
          onChange={(e) => setH(e.target.value)}
          className="h-9 px-2 text-[13px] border border-[#cfccc8] rounded-md bg-white text-[#1e1e24] focus:outline-none focus:border-[#1e4d92]"
        />
        {hOut ? (
          <span className="text-[10px] text-[#b93232]">
            Height must be between {heightMin} and {heightMax}
          </span>
        ) : null}
      </label>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/dimension-input.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/storefront/dimension-input.tsx frontend/src/components/storefront/__tests__/dimension-input.test.tsx
git commit -m "feat(frontend): DimensionInput with bounded width/height"
```

---

### Task 6: `<OptionGroupedForm>` component

**Files:**
- Create: `frontend/src/components/storefront/option-grouped-form.tsx`
- Create: `frontend/src/components/storefront/__tests__/option-grouped-form.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/storefront/__tests__/option-grouped-form.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { OptionGroupedForm } from "@/components/storefront/option-grouped-form";
import type { ProductOption } from "@/lib/types";

const opt = (
  option_key: string,
  options_type: string,
  attrs: { id: string; title: string }[],
): ProductOption => ({
  id: `id-${option_key}`,
  option_key,
  title: option_key,
  options_type,
  sort_order: 0,
  master_option_id: null,
  ops_option_id: null,
  required: false,
  attributes: attrs.map((a, i) => ({
    id: a.id,
    title: a.title,
    sort_order: i,
    ops_attribute_id: null,
  })),
});

describe("OptionGroupedForm", () => {
  it("renders options under their section headers and emits selection", async () => {
    const onChange = vi.fn();
    render(
      <OptionGroupedForm
        options={[
          opt("substrateMaterial", "combo", [
            { id: "a1", title: "SAV" },
            { id: "a2", title: "Vinyl" },
          ]),
          opt("inkFinish", "radio", [
            { id: "a3", title: "Gloss" },
            { id: "a4", title: "Matte" },
          ]),
          opt("cutType", "radio", [
            { id: "a5", title: "Through Cut" },
            { id: "a6", title: "Kiss Cut" },
          ]),
        ]}
        selected={{}}
        onChange={onChange}
      />,
    );

    expect(screen.getByText("Material")).toBeInTheDocument();
    expect(screen.getByText("Cutting")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Matte" }));
    expect(onChange).toHaveBeenLastCalledWith({ "id-inkFinish": "a4" });
  });

  it("hides admin_only options", () => {
    render(
      <OptionGroupedForm
        options={[opt("file_prep", "admin_only", [{ id: "x", title: "x" }])]}
        selected={{}}
        onChange={() => {}}
      />,
    );
    expect(screen.queryByText("file_prep")).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/option-grouped-form.test.tsx
```

Expected: FAIL — component missing.

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/components/storefront/option-grouped-form.tsx
"use client";

import type { ProductOption, ProductOptionAttribute } from "@/lib/types";
import { groupOptionsBySection, SECTION_ORDER, type SectionName } from "@/lib/option-groups";

interface Props {
  options: ProductOption[];
  selected: Record<string, string>;
  onChange: (next: Record<string, string>) => void;
}

export function OptionGroupedForm({ options, selected, onChange }: Props) {
  const grouped = groupOptionsBySection(options);

  const setOpt = (optId: string, attrId: string) => {
    onChange({ ...selected, [optId]: attrId });
  };

  return (
    <div className="flex flex-col gap-6">
      {SECTION_ORDER.map((section) => {
        const opts = grouped[section];
        if (opts.length === 0) return null;
        return (
          <section key={section} className="flex flex-col gap-3">
            <header className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#888894]">
              {section}
            </header>
            <div className="grid grid-cols-1 gap-2">
              {opts.map((opt) => (
                <OptionRow
                  key={opt.id}
                  opt={opt}
                  selectedAttrId={selected[opt.id]}
                  onPick={(attrId) => setOpt(opt.id, attrId)}
                />
              ))}
            </div>
          </section>
        );
      })}
    </div>
  );
}

interface RowProps {
  opt: ProductOption;
  selectedAttrId: string | undefined;
  onPick: (attrId: string) => void;
}

function OptionRow({ opt, selectedAttrId, onPick }: RowProps) {
  const attrs = (opt.attributes ?? []).slice().sort((a, b) => a.sort_order - b.sort_order);
  const type = opt.options_type ?? "combo";

  return (
    <div className="grid grid-cols-[minmax(0,9rem)_1fr] items-center gap-3 px-3 py-2 rounded-md bg-white border border-[#ebe8e3]">
      <div className="min-w-0">
        <div className="truncate text-[13px] font-semibold text-[#1e1e24]">
          {opt.title || opt.option_key}
          {opt.required ? <span className="ml-1 text-[#b93232]">*</span> : null}
        </div>
        <div className="truncate font-mono text-[10px] text-[#b4b4bc]">
          {opt.option_key}
        </div>
      </div>
      {type === "radio" || type === "checkbox" ? (
        <SegmentedAttrs attrs={attrs} selectedAttrId={selectedAttrId} onPick={onPick} />
      ) : (
        <SelectAttrs
          required={opt.required}
          attrs={attrs}
          selectedAttrId={selectedAttrId}
          onPick={onPick}
        />
      )}
    </div>
  );
}

function SegmentedAttrs({
  attrs,
  selectedAttrId,
  onPick,
}: {
  attrs: ProductOptionAttribute[];
  selectedAttrId: string | undefined;
  onPick: (attrId: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1 justify-end">
      {attrs.map((a) => {
        const active = selectedAttrId === a.id;
        return (
          <button
            key={a.id}
            type="button"
            onClick={() => onPick(a.id)}
            className={
              "px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors " +
              (active
                ? "border-[#1e4d92] bg-[#1e4d92] text-white"
                : "border-[#e9e7e3] bg-[#f9f7f4] text-[#484852] hover:border-[#1e4d92] hover:text-[#1e4d92]")
            }
          >
            {a.title}
          </button>
        );
      })}
    </div>
  );
}

function SelectAttrs({
  required,
  attrs,
  selectedAttrId,
  onPick,
}: {
  required: boolean;
  attrs: ProductOptionAttribute[];
  selectedAttrId: string | undefined;
  onPick: (attrId: string) => void;
}) {
  return (
    <select
      value={selectedAttrId ?? ""}
      onChange={(e) => {
        if (e.target.value) onPick(e.target.value);
      }}
      className="h-8 px-2 text-[12px] border border-[#e9e7e3] rounded-md bg-[#f9f7f4] text-[#1e1e24] font-medium focus:outline-none focus:border-[#1e4d92] min-w-0 max-w-full"
    >
      {!required ? <option value="">—</option> : null}
      {attrs.map((a) => (
        <option key={a.id} value={a.id}>
          {a.title}
        </option>
      ))}
    </select>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/option-grouped-form.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/storefront/option-grouped-form.tsx frontend/src/components/storefront/__tests__/option-grouped-form.test.tsx
git commit -m "feat(frontend): print options grouped form (Material/Production/Cutting/Design)"
```

---

### Task 7: `<LivePriceQuote>` component

**Files:**
- Create: `frontend/src/components/storefront/live-price-quote.tsx`
- Create: `frontend/src/components/storefront/__tests__/live-price-quote.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/storefront/__tests__/live-price-quote.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { LivePriceQuote } from "@/components/storefront/live-price-quote";

vi.mock("@/lib/use-debounced-quote", () => ({
  useDebouncedQuote: vi.fn(),
}));
import { useDebouncedQuote } from "@/lib/use-debounced-quote";

describe("LivePriceQuote", () => {
  it("renders a placeholder when not ready", () => {
    (useDebouncedQuote as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue({
      quote: null,
      loading: false,
      error: null,
    });
    render(
      <LivePriceQuote
        productId="p1"
        qty={1}
        width={null}
        height={null}
        selectedAttributeIds={[]}
      />,
    );
    expect(screen.getByText(/enter dimensions/i)).toBeInTheDocument();
  });

  it("renders unit price + breakdown when quote arrives", () => {
    (useDebouncedQuote as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue({
      quote: {
        unit_price: "12.50",
        total: "625.00",
        currency: "USD",
        breakdown: { base: "8.00", area_multiplier: "6.00", setup_cost: "10.00" },
      },
      loading: false,
      error: null,
    });
    render(
      <LivePriceQuote
        productId="p1"
        qty={50}
        width={24}
        height={36}
        selectedAttributeIds={["a1", "a2"]}
      />,
    );
    expect(screen.getByText(/\$625\.00/)).toBeInTheDocument();
    expect(screen.getByText(/12\.50/)).toBeInTheDocument();
    expect(screen.getByText(/setup_cost/i)).toBeInTheDocument();
  });

  it("renders the error message when the quote endpoint fails", () => {
    (useDebouncedQuote as unknown as { mockReturnValue: (v: unknown) => void }).mockReturnValue({
      quote: null,
      loading: false,
      error: "API 400: width is required",
    });
    render(
      <LivePriceQuote
        productId="p1"
        qty={50}
        width={24}
        height={36}
        selectedAttributeIds={[]}
      />,
    );
    expect(screen.getByText(/width is required/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/live-price-quote.test.tsx
```

Expected: FAIL — component missing.

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/components/storefront/live-price-quote.tsx
"use client";

import { useDebouncedQuote } from "@/lib/use-debounced-quote";

interface Props {
  productId: string;
  qty: number;
  width: number | null;
  height: number | null;
  selectedAttributeIds: string[];
}

export function LivePriceQuote({
  productId,
  qty,
  width,
  height,
  selectedAttributeIds,
}: Props) {
  const ready = qty > 0 && width != null && height != null && width > 0 && height > 0;
  const { quote, loading, error } = useDebouncedQuote({
    enabled: ready,
    body: {
      product_id: productId,
      qty,
      width: width ?? undefined,
      height: height ?? undefined,
      selected_attribute_ids: selectedAttributeIds,
    },
  });

  if (!ready) {
    return (
      <div className="px-4 py-3 rounded-md border border-dashed border-[#cfccc8] text-[12px] text-[#888894]">
        Enter dimensions and quantity to see your price
      </div>
    );
  }
  if (error) {
    return (
      <div className="px-4 py-3 rounded-md border border-[#b93232] bg-[#fdeded] text-[12px] text-[#b93232]">
        {error}
      </div>
    );
  }
  if (loading || !quote) {
    return (
      <div className="px-4 py-3 rounded-md border border-[#cfccc8] text-[12px] text-[#888894]">
        Pricing…
      </div>
    );
  }
  return (
    <div className="px-4 py-3 rounded-md border border-[#1e4d92] bg-[#eef4fb]">
      <div className="flex items-baseline justify-between">
        <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#1e4d92]">
          Total
        </div>
        <div className="text-[24px] font-extrabold text-[#1e1e24]">${quote.total}</div>
      </div>
      <div className="mt-1 text-[12px] text-[#484852]">
        ${quote.unit_price} per unit · {quote.currency}
      </div>
      <details className="mt-3 text-[11px]">
        <summary className="cursor-pointer text-[#1e4d92] font-semibold">Breakdown</summary>
        <ul className="mt-2 grid grid-cols-2 gap-1 font-mono text-[11px] text-[#484852]">
          {Object.entries(quote.breakdown).map(([k, v]) => (
            <li key={k}>
              {k}: {typeof v === "object" ? JSON.stringify(v) : String(v)}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/live-price-quote.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/storefront/live-price-quote.tsx frontend/src/components/storefront/__tests__/live-price-quote.test.tsx
git commit -m "feat(frontend): LivePriceQuote with breakdown disclosure"
```

---

### Task 8: `<PriceTierTable>` component for apparel

**Files:**
- Create: `frontend/src/components/storefront/price-tier-table.tsx`
- Create: `frontend/src/components/storefront/__tests__/price-tier-table.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/storefront/__tests__/price-tier-table.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { PriceTierTable } from "@/components/storefront/price-tier-table";

describe("PriceTierTable", () => {
  it("renders the qty bands with currency", () => {
    render(
      <PriceTierTable
        tiers={[
          { group_name: "MSRP", qty_min: 1, qty_max: 11, price: "24.98", currency: "USD" },
          { group_name: "MSRP", qty_min: 12, qty_max: 2147483647, price: "19.98", currency: "USD" },
        ]}
      />,
    );
    expect(screen.getByText("1 – 11")).toBeInTheDocument();
    expect(screen.getByText("12+")).toBeInTheDocument();
    expect(screen.getByText("$24.98")).toBeInTheDocument();
    expect(screen.getByText("$19.98")).toBeInTheDocument();
  });

  it("renders nothing when no tiers", () => {
    const { container } = render(<PriceTierTable tiers={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/price-tier-table.test.tsx
```

Expected: FAIL — component missing.

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/components/storefront/price-tier-table.tsx
"use client";

import type { VariantPriceTier } from "@/lib/types";

interface Props {
  tiers: VariantPriceTier[];
}

const UNBOUNDED = 2147483647;

export function PriceTierTable({ tiers }: Props) {
  if (tiers.length === 0) return null;
  const sorted = [...tiers].sort((a, b) => a.qty_min - b.qty_min);

  return (
    <div className="rounded-md border border-[#cfccc8] overflow-hidden">
      <table className="w-full text-[12px]">
        <thead className="bg-[#f2f0ed] text-[10px] font-bold uppercase tracking-[0.1em] text-[#484852]">
          <tr>
            <th className="text-left px-3 py-1.5">Quantity</th>
            <th className="text-right px-3 py-1.5">Price each</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((t) => (
            <tr key={`${t.group_name}-${t.qty_min}`} className="odd:bg-white even:bg-[#f9f7f4]">
              <td className="px-3 py-1.5 font-mono">
                {t.qty_max >= UNBOUNDED ? `${t.qty_min}+` : `${t.qty_min} – ${t.qty_max}`}
              </td>
              <td className="px-3 py-1.5 text-right font-semibold text-[#1e1e24]">
                ${t.price}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/price-tier-table.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/storefront/price-tier-table.tsx frontend/src/components/storefront/__tests__/price-tier-table.test.tsx
git commit -m "feat(frontend): PriceTierTable for apparel variant qty bands"
```

---

### Task 9: `<ApparelDetailPanel>` wrapper

**Files:**
- Create: `frontend/src/components/storefront/apparel-detail-panel.tsx`

- [ ] **Step 1: Write the component**

```tsx
// frontend/src/components/storefront/apparel-detail-panel.tsx
"use client";

import { useState } from "react";
import type { Product, Variant } from "@/lib/types";
import { VariantPicker } from "@/components/storefront/variant-picker";
import { PriceBlock } from "@/components/storefront/price-block";
import { PriceTierTable } from "@/components/storefront/price-tier-table";

interface Props {
  product: Product;
}

export function ApparelDetailPanel({ product }: Props) {
  const [selectedVariantId, setSelectedVariantId] = useState<string | null>(
    product.variants[0]?.id ?? null,
  );
  const selected: Variant | null =
    product.variants.find((v) => v.id === selectedVariantId) ?? null;

  return (
    <div className="flex flex-col gap-6">
      <PriceBlock variant={selected} fallback={product.variants} adjustment={0} />

      {product.variants.length > 0 && (
        <div className="py-5 border-t border-dashed border-[#cfccc8]">
          <VariantPicker
            variants={product.variants}
            selectedVariantId={selectedVariantId}
            onSelect={setSelectedVariantId}
          />
        </div>
      )}

      {selected ? <PriceTierTable tiers={selected.prices} /> : null}

      {product.apparel_details ? (
        <ApparelMeta details={product.apparel_details} />
      ) : null}
    </div>
  );
}

function ApparelMeta({
  details,
}: {
  details: NonNullable<Product["apparel_details"]>;
}) {
  const fabricEntries = Object.entries(details.fabric_specs ?? {});
  return (
    <div className="pt-5 border-t border-dashed border-[#cfccc8] flex flex-col gap-3">
      <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#888894]">
        Specs
      </div>
      <div className="flex flex-wrap gap-2">
        {details.apparel_style ? <Badge>{details.apparel_style}</Badge> : null}
        {details.is_closeout ? <Badge tone="warn">Closeout</Badge> : null}
        {details.is_hazmat ? <Badge tone="warn">Hazmat</Badge> : null}
        {details.is_caution ? <Badge tone="warn">Caution</Badge> : null}
      </div>
      {fabricEntries.length > 0 ? (
        <ul className="grid grid-cols-2 gap-1 font-mono text-[11px] text-[#484852]">
          {fabricEntries.map(([k, v]) => (
            <li key={k}>
              {k}: {String(v)}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function Badge({
  children,
  tone = "default",
}: {
  children: React.ReactNode;
  tone?: "default" | "warn";
}) {
  const cls =
    tone === "warn"
      ? "border-[#b93232] bg-[#fdeded] text-[#b93232]"
      : "border-[#1e4d92] bg-[#eef4fb] text-[#1e4d92]";
  return (
    <span
      className={`px-2 py-0.5 rounded text-[10px] font-bold tracking-wide uppercase border ${cls}`}
    >
      {children}
    </span>
  );
}
```

- [ ] **Step 2: Verify the typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/storefront/apparel-detail-panel.tsx
git commit -m "feat(frontend): ApparelDetailPanel composes VariantPicker + PriceTierTable + meta"
```

---

### Task 10: `<PrintDetailPanel>` wrapper

**Files:**
- Create: `frontend/src/components/storefront/print-detail-panel.tsx`

- [ ] **Step 1: Write the component**

```tsx
// frontend/src/components/storefront/print-detail-panel.tsx
"use client";

import { useState } from "react";
import type { Product } from "@/lib/types";
import { DimensionInput, type DimensionInputValue } from "@/components/storefront/dimension-input";
import { OptionGroupedForm } from "@/components/storefront/option-grouped-form";
import { LivePriceQuote } from "@/components/storefront/live-price-quote";

interface Props {
  product: Product;
}

const num = (s: string | null | undefined): number | null =>
  s == null || s === "" ? null : Number(s);

export function PrintDetailPanel({ product }: Props) {
  const detail = product.print_details;
  const [dim, setDim] = useState<DimensionInputValue>({ width: null, height: null });
  const [qty, setQty] = useState<number>(1);
  const [selected, setSelected] = useState<Record<string, string>>({});

  const selectedAttributeIds = Object.values(selected).filter((v): v is string => !!v);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-3">
        <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#888894]">
          Size
        </div>
        <DimensionInput
          width={dim.width}
          height={dim.height}
          widthMin={num(detail?.width_min ?? null)}
          widthMax={num(detail?.width_max ?? null)}
          heightMin={num(detail?.height_min ?? null)}
          heightMax={num(detail?.height_max ?? null)}
          onChange={setDim}
        />
      </div>

      <div className="flex flex-col gap-3">
        <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#888894]">
          Quantity
        </div>
        <input
          aria-label="Quantity"
          type="number"
          min={1}
          step={1}
          value={qty}
          onChange={(e) => setQty(Math.max(1, Number(e.target.value) || 1))}
          className="h-9 w-32 px-2 text-[13px] border border-[#cfccc8] rounded-md bg-white text-[#1e1e24] focus:outline-none focus:border-[#1e4d92]"
        />
      </div>

      <OptionGroupedForm
        options={product.options}
        selected={selected}
        onChange={setSelected}
      />

      <LivePriceQuote
        productId={product.id}
        qty={qty}
        width={dim.width}
        height={dim.height}
        selectedAttributeIds={selectedAttributeIds}
      />
    </div>
  );
}
```

- [ ] **Step 2: Verify the typecheck**

```bash
cd frontend && npx tsc --noEmit
```

Expected: clean.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/storefront/print-detail-panel.tsx
git commit -m "feat(frontend): PrintDetailPanel composes DimensionInput + OptionGroupedForm + LivePriceQuote"
```

---

### Task 11: `<ProductDetailPanel>` dispatcher

**Files:**
- Create: `frontend/src/components/storefront/product-detail-panel.tsx`
- Create: `frontend/src/components/storefront/__tests__/product-detail-panel.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/storefront/__tests__/product-detail-panel.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Product } from "@/lib/types";
import { ProductDetailPanel } from "@/components/storefront/product-detail-panel";

vi.mock("@/components/storefront/apparel-detail-panel", () => ({
  ApparelDetailPanel: () => <div data-testid="apparel-panel" />,
}));
vi.mock("@/components/storefront/print-detail-panel", () => ({
  PrintDetailPanel: () => <div data-testid="print-panel" />,
}));

const baseProduct: Product = {
  id: "p1",
  supplier_id: "s1",
  supplier_name: "x",
  supplier_sku: "x",
  product_name: "x",
  brand: null,
  category: null,
  category_id: null,
  description: null,
  product_type: "apparel",
  pricing_method: "tiered_variants",
  image_url: null,
  ops_product_id: null,
  external_catalogue: null,
  last_synced: null,
  archived_at: null,
  variants: [],
  images: [],
  options: [],
  apparel_details: null,
  print_details: null,
  sizes: [],
};

describe("ProductDetailPanel", () => {
  it("renders apparel panel for apparel product", () => {
    render(<ProductDetailPanel product={{ ...baseProduct, product_type: "apparel" }} />);
    expect(screen.getByTestId("apparel-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("print-panel")).toBeNull();
  });

  it("renders print panel for print product", () => {
    render(<ProductDetailPanel product={{ ...baseProduct, product_type: "print" }} />);
    expect(screen.getByTestId("print-panel")).toBeInTheDocument();
    expect(screen.queryByTestId("apparel-panel")).toBeNull();
  });

  it("falls back to apparel for unknown product_type", () => {
    render(
      <ProductDetailPanel
        product={{ ...baseProduct, product_type: "promo" as Product["product_type"] }}
      />,
    );
    expect(screen.getByTestId("apparel-panel")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/product-detail-panel.test.tsx
```

Expected: FAIL — module missing.

- [ ] **Step 3: Implement the dispatcher**

```tsx
// frontend/src/components/storefront/product-detail-panel.tsx
"use client";

import type { Product } from "@/lib/types";
import { ApparelDetailPanel } from "@/components/storefront/apparel-detail-panel";
import { PrintDetailPanel } from "@/components/storefront/print-detail-panel";

interface Props {
  product: Product;
}

export function ProductDetailPanel({ product }: Props) {
  if (product.product_type === "print") {
    return <PrintDetailPanel product={product} />;
  }
  return <ApparelDetailPanel product={product} />;
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/product-detail-panel.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/storefront/product-detail-panel.tsx frontend/src/components/storefront/__tests__/product-detail-panel.test.tsx
git commit -m "feat(frontend): ProductDetailPanel dispatches by product_type"
```

---

### Task 12: Wire the existing PDP route to use `<ProductDetailPanel>`

**Files:**
- Modify: `frontend/src/app/storefront/vg/product/[product_id]/page.tsx`

- [ ] **Step 1: Read the current file**

```bash
cd frontend && cat src/app/storefront/vg/product/\[product_id\]/page.tsx
```

Confirm it currently builds the `info` JSX inline using `PriceBlock`, `VariantPicker`, `ProductOptions`. We replace that `info` section with `<ProductDetailPanel>`. Header (brand + title + SKU + badges) and CTAs stay inline.

- [ ] **Step 2: Apply the edit**

In `frontend/src/app/storefront/vg/product/[product_id]/page.tsx`:

1. At the top of the imports, add:
   ```tsx
   import { ProductDetailPanel } from "@/components/storefront/product-detail-panel";
   ```
2. Remove the imports for `VariantPicker`, `PriceBlock`, `ProductOptions` (now consumed by the panel children).
3. Remove the `optionAdj` state and `priceLookup` state and the `useEffect` that fetches `/api/products/{id}/options-config`. Those were used by the old `<ProductOptions>` integration; the new panels manage their own pricing flow.
4. Replace the body of `info` so it reads:
   ```tsx
   const info = (
     <div className="flex flex-col gap-6">
       <div>
         {product.brand && (
           <div className="text-[11px] font-bold uppercase tracking-[0.15em] text-[#1e4d92] mb-2">
             {product.brand}
           </div>
         )}
         <h1 className="text-[28px] font-extrabold tracking-[-0.03em] leading-tight text-[#1e1e24]">
           {product.product_name}
         </h1>
         <div className="flex items-center gap-3 mt-2">
           <div className="font-mono text-[12px] text-[#888894]">
             {product.supplier_sku} · {product.product_type}
           </div>
           {product.external_catalogue === 1 && (
             <span className="px-2 py-0.5 rounded bg-[#eef4fb] border border-[#1e4d92] text-[#1e4d92] text-[10px] font-bold tracking-wide uppercase">
               External Catalogue
             </span>
           )}
         </div>
       </div>

       <ProductDetailPanel product={product} />

       <div className="flex gap-3 pt-2">
         <button
           type="button"
           onClick={() => router.back()}
           className="px-5 py-3 rounded-md border border-[#cfccc8] text-[#1e1e24] text-[13px] font-semibold hover:border-[#1e4d92] hover:text-[#1e4d92]"
         >
           ← Back
         </button>
         <button
           type="button"
           disabled
           className="flex-1 px-5 py-3 rounded-md bg-[#1e4d92] text-white text-[13px] font-semibold opacity-60 cursor-not-allowed"
           title="Quote flow coming in future phase"
         >
           Add to quote
         </button>
       </div>
     </div>
   );
   ```

- [ ] **Step 3: Manual sanity check**

```bash
cd frontend && npm run dev
```

Then in another shell, hit two real product IDs (one apparel, one print) under `http://localhost:3000/storefront/vg/product/<id>`. Confirm the apparel id renders the variant picker + qty tier table, the print id renders the dimension input + grouped options + live quote, and the route is the same in both cases. Stop the dev server with Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/storefront/vg/product/\[product_id\]/page.tsx
git commit -m "feat(frontend): PDP route delegates body to ProductDetailPanel"
```

---

### Task 13: `<ProductTypeFilter>` pill for the catalog list

**Files:**
- Create: `frontend/src/components/storefront/product-type-filter.tsx`
- Create: `frontend/src/components/storefront/__tests__/product-type-filter.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/storefront/__tests__/product-type-filter.test.tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProductTypeFilter } from "@/components/storefront/product-type-filter";

describe("ProductTypeFilter", () => {
  it("renders an All pill plus one pill per available type", async () => {
    const onChange = vi.fn();
    render(
      <ProductTypeFilter available={["apparel", "print"]} value={null} onChange={onChange} />,
    );
    expect(screen.getByRole("button", { name: /all/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /apparel/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /print/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /print/i }));
    expect(onChange).toHaveBeenLastCalledWith("print");
  });

  it("clicking the active pill clears the filter", async () => {
    const onChange = vi.fn();
    render(
      <ProductTypeFilter available={["apparel", "print"]} value="apparel" onChange={onChange} />,
    );
    await userEvent.click(screen.getByRole("button", { name: /apparel/i }));
    expect(onChange).toHaveBeenLastCalledWith(null);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/product-type-filter.test.tsx
```

Expected: FAIL — component missing.

- [ ] **Step 3: Implement the component**

```tsx
// frontend/src/components/storefront/product-type-filter.tsx
"use client";

import type { ProductType } from "@/lib/types";

const LABELS: Record<ProductType, string> = {
  apparel: "Apparel",
  print: "Print",
  template: "Template",
  promo: "Promo",
};

interface Props {
  available: ProductType[];
  value: ProductType | null;
  onChange: (value: ProductType | null) => void;
}

export function ProductTypeFilter({ available, value, onChange }: Props) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <Pill active={value === null} onClick={() => onChange(null)}>
        All
      </Pill>
      {available.map((t) => (
        <Pill
          key={t}
          active={value === t}
          onClick={() => onChange(value === t ? null : t)}
        >
          {LABELS[t]}
        </Pill>
      ))}
    </div>
  );
}

function Pill({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={
        "px-3 py-1 rounded-full border text-[12px] font-semibold transition-colors " +
        (active
          ? "border-[#1e4d92] bg-[#1e4d92] text-white"
          : "border-[#cfccc8] bg-white text-[#1e1e24] hover:border-[#1e4d92] hover:text-[#1e4d92]")
      }
    >
      {children}
    </button>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd frontend && npm run test -- src/components/storefront/__tests__/product-type-filter.test.tsx
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/storefront/product-type-filter.tsx frontend/src/components/storefront/__tests__/product-type-filter.test.tsx
git commit -m "feat(frontend): ProductTypeFilter pill"
```

---

### Task 14: Wire `<ProductTypeFilter>` into the storefront catalog and category pages

**Files:**
- Modify: `frontend/src/app/storefront/vg/page.tsx`
- Modify: `frontend/src/app/storefront/vg/category/[category_id]/page.tsx`

- [ ] **Step 1: Read the current pages**

```bash
cd frontend && cat src/app/storefront/vg/page.tsx
cd frontend && cat src/app/storefront/vg/category/\[category_id\]/page.tsx
```

Both pages call `api<ProductListItem[]>("/api/products?…")`. We add a local `productType` state and a derived list filtered by `product_type`. The list endpoint already returns `product_type` per item (Task 2 added that to the type), so no backend change is needed.

- [ ] **Step 2: Apply the edits**

In each of the two pages:

1. Add the import:
   ```tsx
   import { ProductTypeFilter } from "@/components/storefront/product-type-filter";
   import type { ProductType } from "@/lib/types";
   ```
2. Add state next to the other filter state:
   ```tsx
   const [productType, setProductType] = useState<ProductType | null>(null);
   ```
3. Compute available types from the loaded list:
   ```tsx
   const availableTypes = useMemo(
     () =>
       Array.from(new Set(items.map((i) => i.product_type))) as ProductType[],
     [items],
   );
   const filteredItems = useMemo(
     () => (productType ? items.filter((i) => i.product_type === productType) : items),
     [items, productType],
   );
   ```
4. Render the filter just above the existing grid (place it inside whatever toolbar / heading wrapper the page already uses):
   ```tsx
   <ProductTypeFilter
     available={availableTypes}
     value={productType}
     onChange={setProductType}
   />
   ```
5. Replace the variable used to render the grid: change `items.map(...)` to `filteredItems.map(...)`.

If the page already has a `useMemo` import, reuse it; otherwise, add `import { useMemo, useState } from "react";` at the top.

- [ ] **Step 3: Manual smoke**

```bash
cd frontend && npm run dev
```

Open `http://localhost:3000/storefront/vg`. Confirm the filter pill row appears above the grid, only shows pills for product types actually present, and clicking a pill narrows the list.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/storefront/vg/page.tsx frontend/src/app/storefront/vg/category/\[category_id\]/page.tsx
git commit -m "feat(frontend): catalog + category pages get product_type filter pill"
```

---

### Task 15: Playwright e2e — apparel PDP variant selection

**Files:**
- Create: `frontend/e2e/fixtures/apparel-product.json`
- Create: `frontend/e2e/apparel-pdp.spec.ts`

- [ ] **Step 1: Create the fixture**

`frontend/e2e/fixtures/apparel-product.json`:

```json
{
  "id": "00000000-0000-0000-0000-0000000000a1",
  "supplier_id": "00000000-0000-0000-0000-0000000000s1",
  "supplier_name": "SanMar",
  "supplier_sku": "PC61",
  "product_name": "Heavyweight Polo",
  "brand": "Mercer+Mettle",
  "category": null,
  "category_id": null,
  "description": "<p>A heavyweight polo.</p>",
  "product_type": "apparel",
  "pricing_method": "tiered_variants",
  "image_url": "https://cdnm.sanmar.com/MM1000.jpg",
  "ops_product_id": null,
  "external_catalogue": null,
  "last_synced": null,
  "archived_at": null,
  "variants": [
    {
      "id": "v1",
      "color": "Deep Black",
      "size": "S",
      "sku": "PC61-DB-S",
      "base_price": 24.98,
      "inventory": null,
      "warehouse": null,
      "part_id": "1878771",
      "gtin": "00191265938235",
      "flags": { "pms_color": "BLACK C", "standard_color": "Deep Black" },
      "prices": [
        { "group_name": "MSRP", "qty_min": 1, "qty_max": 11, "price": "24.98", "currency": "USD" },
        { "group_name": "MSRP", "qty_min": 12, "qty_max": 2147483647, "price": "19.98", "currency": "USD" }
      ]
    },
    {
      "id": "v2",
      "color": "Deep Black",
      "size": "M",
      "sku": "PC61-DB-M",
      "base_price": 24.98,
      "inventory": null,
      "warehouse": null,
      "part_id": "1878772",
      "gtin": null,
      "flags": null,
      "prices": [
        { "group_name": "MSRP", "qty_min": 1, "qty_max": 11, "price": "24.98", "currency": "USD" }
      ]
    }
  ],
  "images": [],
  "options": [],
  "apparel_details": {
    "ps_part_id": "1878771",
    "apparel_style": "Mens",
    "is_closeout": false,
    "is_hazmat": null,
    "is_caution": false,
    "caution_comment": null,
    "is_on_demand": null,
    "fabric_specs": { "weight_oz": 8.1 },
    "fob_points": null,
    "keywords": null
  },
  "print_details": null,
  "sizes": []
}
```

- [ ] **Step 2: Write the spec**

```ts
// frontend/e2e/apparel-pdp.spec.ts
import { test, expect } from "@playwright/test";
import apparel from "./fixtures/apparel-product.json";

test.describe("Apparel PDP", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/products/00000000-0000-0000-0000-0000000000a1", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(apparel),
      });
    });
    // Block other backend calls so the test does not require a running backend.
    await page.route("**/api/products/00000000-0000-0000-0000-0000000000a1/options-config", (r) =>
      r.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
    );
    await page.route("**/api/categories/**", (r) =>
      r.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
    );
  });

  test("renders the variant picker and updates the tier table on selection", async ({ page }) => {
    await page.goto("/storefront/vg/product/00000000-0000-0000-0000-0000000000a1");
    await expect(page.getByRole("heading", { name: "Heavyweight Polo" })).toBeVisible();

    // Variant picker buttons
    await expect(page.getByRole("button", { name: "Deep Black" })).toBeVisible();
    const sButton = page.getByRole("button", { name: "S", exact: true });
    await expect(sButton).toBeVisible();

    // Default = first variant; tier table shows two bands.
    await expect(page.getByText("1 – 11")).toBeVisible();
    await expect(page.getByText("12+")).toBeVisible();

    // Pick size M → tier table collapses to one band (per fixture).
    await page.getByRole("button", { name: "M", exact: true }).click();
    await expect(page.getByText("1 – 11")).toBeVisible();
    await expect(page.getByText("12+")).not.toBeVisible();

    // Apparel meta shows Mens badge.
    await expect(page.getByText("Mens")).toBeVisible();
  });
});
```

- [ ] **Step 3: Run the spec**

```bash
cd frontend && npm run test:e2e -- e2e/apparel-pdp.spec.ts
```

Expected: PASS. The webServer block in `playwright.config.ts` boots `npm run dev` automatically; ensure no other dev server is bound to port 3000 first.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/fixtures/apparel-product.json frontend/e2e/apparel-pdp.spec.ts
git commit -m "test(frontend): playwright e2e for apparel PDP"
```

---

### Task 16: Playwright e2e — print PDP dimension + options + live quote

**Files:**
- Create: `frontend/e2e/fixtures/print-product.json`
- Create: `frontend/e2e/fixtures/quote-response.json`
- Create: `frontend/e2e/print-pdp.spec.ts`

- [ ] **Step 1: Create the print fixture**

`frontend/e2e/fixtures/print-product.json`:

```json
{
  "id": "00000000-0000-0000-0000-0000000000b1",
  "supplier_id": "00000000-0000-0000-0000-0000000000s1",
  "supplier_name": "VG OPS",
  "supplier_sku": "131",
  "product_name": "Decals - General Performance",
  "brand": null,
  "category": null,
  "category_id": null,
  "description": null,
  "product_type": "print",
  "pricing_method": "formula",
  "image_url": null,
  "ops_product_id": "131",
  "external_catalogue": 1,
  "last_synced": null,
  "archived_at": null,
  "variants": [],
  "images": [],
  "options": [
    {
      "id": "opt-substrate",
      "option_key": "substrateMaterial",
      "title": "Substrate",
      "options_type": "combo",
      "sort_order": 0,
      "master_option_id": null,
      "ops_option_id": null,
      "required": false,
      "attributes": [
        { "id": "a-sav", "title": "SAV", "sort_order": 0, "ops_attribute_id": null },
        { "id": "a-vinyl", "title": "Vinyl", "sort_order": 1, "ops_attribute_id": null }
      ]
    },
    {
      "id": "opt-ink",
      "option_key": "inkFinish",
      "title": "Ink Finish",
      "options_type": "radio",
      "sort_order": 1,
      "master_option_id": null,
      "ops_option_id": null,
      "required": false,
      "attributes": [
        { "id": "a-gloss", "title": "Gloss", "sort_order": 0, "ops_attribute_id": null },
        { "id": "a-matte", "title": "Matte", "sort_order": 1, "ops_attribute_id": null }
      ]
    }
  ],
  "apparel_details": null,
  "print_details": {
    "ops_product_id_int": 131,
    "default_category_id": 22,
    "external_catalogue": 1,
    "width_min": "1",
    "width_max": "96",
    "height_min": "1",
    "height_max": "96",
    "formula": null,
    "size_template_id": null
  },
  "sizes": [
    {
      "id": "sz1",
      "ops_size_id": 160,
      "size_title": "Custom Size",
      "size_width": "0",
      "size_height": "0",
      "width_min": "1",
      "width_max": "96",
      "height_min": "1",
      "height_max": "96",
      "sort_order": 0
    }
  ]
}
```

- [ ] **Step 2: Create the quote fixture**

`frontend/e2e/fixtures/quote-response.json`:

```json
{
  "unit_price": "12.50",
  "total": "625.00",
  "currency": "USD",
  "breakdown": {
    "base": "8.00",
    "area_multiplier": "6.00",
    "setup_cost": "10.00"
  }
}
```

- [ ] **Step 3: Write the spec**

```ts
// frontend/e2e/print-pdp.spec.ts
import { test, expect } from "@playwright/test";
import printProduct from "./fixtures/print-product.json";
import quote from "./fixtures/quote-response.json";

test.describe("Print PDP", () => {
  test.beforeEach(async ({ page }) => {
    await page.route("**/api/products/00000000-0000-0000-0000-0000000000b1", (r) =>
      r.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(printProduct),
      }),
    );
    await page.route("**/api/products/00000000-0000-0000-0000-0000000000b1/options-config", (r) =>
      r.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
    );
    await page.route("**/api/categories/**", (r) =>
      r.fulfill({ status: 404, contentType: "application/json", body: "{}" }),
    );
  });

  test("renders dimension input + options + live quote", async ({ page }) => {
    let quoteCalls = 0;
    await page.route("**/api/pricing/quote", async (route) => {
      quoteCalls += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify(quote),
      });
    });

    await page.goto("/storefront/vg/product/00000000-0000-0000-0000-0000000000b1");
    await expect(page.getByRole("heading", { name: "Decals - General Performance" })).toBeVisible();

    // Placeholder until dimensions filled.
    await expect(page.getByText(/enter dimensions/i)).toBeVisible();
    expect(quoteCalls).toBe(0);

    // Fill width + height; quote should be requested.
    await page.getByLabel("Width").fill("24");
    await page.getByLabel("Height").fill("36");
    await expect(page.getByText("$625.00")).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/12\.50 per unit/)).toBeVisible();
    await expect(page.getByText(/Material/)).toBeVisible();

    // Selecting an option also re-requests.
    const before = quoteCalls;
    await page.getByRole("button", { name: "Matte" }).click();
    await expect.poll(() => quoteCalls).toBeGreaterThan(before);
  });
});
```

- [ ] **Step 4: Run the spec**

```bash
cd frontend && npm run test:e2e -- e2e/print-pdp.spec.ts
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/e2e/fixtures/print-product.json frontend/e2e/fixtures/quote-response.json frontend/e2e/print-pdp.spec.ts
git commit -m "test(frontend): playwright e2e for print PDP with live quote"
```

---

### Task 17: Playwright e2e — catalog filter narrows the list

**Files:**
- Create: `frontend/e2e/catalog-filter.spec.ts`

- [ ] **Step 1: Write the spec**

```ts
// frontend/e2e/catalog-filter.spec.ts
import { test, expect } from "@playwright/test";

const items = [
  {
    id: "00000000-0000-0000-0000-0000000000a1",
    supplier_id: "s1",
    supplier_name: "SanMar",
    supplier_sku: "PC61",
    product_name: "Apparel One",
    brand: "Mercer+Mettle",
    category_id: null,
    product_type: "apparel",
    pricing_method: "tiered_variants",
    image_url: null,
    ops_product_id: null,
    external_catalogue: null,
    variant_count: 4,
    price_min: 19.98,
    price_max: 24.98,
    total_inventory: 1000,
    archived_at: null,
  },
  {
    id: "00000000-0000-0000-0000-0000000000b1",
    supplier_id: "s1",
    supplier_name: "VG OPS",
    supplier_sku: "131",
    product_name: "Decals - General",
    brand: null,
    category_id: null,
    product_type: "print",
    pricing_method: "formula",
    image_url: null,
    ops_product_id: "131",
    external_catalogue: 1,
    variant_count: 0,
    price_min: null,
    price_max: null,
    total_inventory: 0,
    archived_at: null,
  },
];

test("catalog filter narrows the list by product_type", async ({ page }) => {
  await page.route("**/api/products?**", (r) =>
    r.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(items),
    }),
  );
  await page.route("**/api/categories?**", (r) =>
    r.fulfill({ status: 200, contentType: "application/json", body: "[]" }),
  );

  await page.goto("/storefront/vg");
  await expect(page.getByText("Apparel One")).toBeVisible();
  await expect(page.getByText("Decals - General")).toBeVisible();

  await page.getByRole("button", { name: "Print" }).click();
  await expect(page.getByText("Decals - General")).toBeVisible();
  await expect(page.getByText("Apparel One")).not.toBeVisible();

  // Click the active pill clears the filter.
  await page.getByRole("button", { name: "Print" }).click();
  await expect(page.getByText("Apparel One")).toBeVisible();
});
```

- [ ] **Step 2: Run the spec**

```bash
cd frontend && npm run test:e2e -- e2e/catalog-filter.spec.ts
```

Expected: PASS. If the catalog page caches the route by URL pattern the test mock does not match, broaden the route pattern in the test to `"**/api/products*"` and re-run.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/catalog-filter.spec.ts
git commit -m "test(frontend): playwright e2e for catalog product_type filter"
```

---

### Task 18: Final regression sweep + frontend runbook

**Files:**
- Create: `frontend/docs/pdp-runbook.md`
- Modify: existing tests if any regression surfaces

- [ ] **Step 1: Run the full Vitest suite**

```bash
cd frontend && npm run test
```

Expected: every Vitest test passes.

- [ ] **Step 2: Run the full Playwright suite**

```bash
cd frontend && npm run test:e2e
```

Expected: all three e2e specs pass.

- [ ] **Step 3: Run the typecheck and lint**

```bash
cd frontend && npx tsc --noEmit && npm run lint
```

Expected: clean.

- [ ] **Step 4: Write the runbook**

Create `frontend/docs/pdp-runbook.md`:

```markdown
# Polymorphic PDP — Frontend Runbook

## What changed
- `/storefront/vg/product/[product_id]` now renders apparel **and** print products.
- The `info` slot delegates to `<ProductDetailPanel>` which dispatches by
  `product.product_type`:
  - `apparel` → `<ApparelDetailPanel>` (variant picker + tier table + meta).
  - `print`   → `<PrintDetailPanel>` (dimension input + grouped options + live quote).
- `<LivePriceQuote>` calls `POST /api/pricing/quote` with a 250 ms debounce.
- Catalog list (`/storefront/vg`) and category list pages get a
  `<ProductTypeFilter>` pill row above the grid.

## What does NOT change
- `<PDPLayout>`, `<ImageGallery>`, `<DescriptionHtml>`, `<RelatedProducts>`,
  `<TopBar>`, breadcrumbs, the storefront shell.
- Existing apparel-only callers of `<VariantPicker>` and `<ProductOptions>`.
- The admin product page (`/(admin)/products/[id]`).

## Local development
1. Backend Phase 1 + 2 + 3 + 4 must be running on :8000.
2. `NEXT_PUBLIC_API_URL=http://localhost:8000` in `frontend/.env.local`.
3. `cd frontend && npm run dev` boots the storefront on :3000.

## Tests
- Vitest unit + integration: `npm run test`.
- Playwright e2e: `npm run test:e2e`. The e2e tests mock `fetch` at the
  Playwright route layer, so they do **not** require a running backend; the
  `webServer` block in `playwright.config.ts` boots `npm run dev` on demand.

## Rollback
- Revert this branch and restart Next.js. No data migrations to undo.
```

- [ ] **Step 5: Commit**

```bash
git add frontend/docs/pdp-runbook.md
git commit -m "docs(frontend): polymorphic PDP runbook"
```

---

## Self-Review

**1. Spec coverage:**

| Spec section | Implemented in |
|--------------|----------------|
| §8 single `/products/[id]` route | Task 12 wires the existing `/storefront/vg/product/[product_id]` route to delegate to `<ProductDetailPanel>`. The plan uses the existing storefront route rather than a new top-level `/products/[id]`; that mirrors the live codebase and is called out in the file structure. |
| §8 `<ProductDetailPanel>` dispatch by `product.product_type` | Task 11 |
| §8 apparel: `<VariantPicker>` (existing) + `<PriceTierTable>` | Tasks 8, 9 |
| §8 apparel: color hex from `pms_color` | Variant `flags.pms_color` is exposed in the type extensions (Task 2) and rendered in `ApparelMeta`. The existing `<VariantPicker>` is left intact; richer swatch coloring is noted as a follow-up because the live VG shop uses textual color buttons today. |
| §8 print: `<DimensionInput>` bounded by `print_details.width_min/max + height_min/max` | Tasks 5, 10 |
| §8 print: `<OptionGroupedForm>` grouped Material/Production/Cutting/Design + options_type rendering | Tasks 3, 6 |
| §8 print: `<LivePriceQuote>` debounced `/api/pricing/quote` | Tasks 4, 7, 10 |
| §8 catalog filter pill | Tasks 13, 14 |
| §9 `PriceQuote` response shape | Task 2 (`PriceQuote` type) + Task 4 (hook) |
| §11.4 Playwright e2e coverage (apparel selection updates price; print dimension+options updates price; both share the same route; catalog filter narrows the list) | Tasks 15, 16, 17 |
| §12 Phase 5 frontend rollout | All tasks |

Spec gap: §8 mentions a `<RawAttributesAccordion>` (collapsed dev/admin block dumping `flags` + `raw_payload`). The plan does not implement it because it is a developer-only debug aid, not part of the customer-facing PDP. Re-add as a follow-up plan if needed.

**2. Placeholder scan:** No `TBD`, no `TODO`, no "implement later". Every task carries the actual code, the actual file path, and the exact run / commit commands. Test fixtures are written out in full inline.

**3. Type consistency:**
- `Product`, `Variant`, `VariantPriceTier`, `ApparelDetails`, `PrintDetails`, `ProductSize`, `PriceQuote`, `PriceQuoteRequest`, `ProductType`, `PricingMethod` are defined in Task 2 and used unchanged through Tasks 4–17.
- `useDebouncedQuote` arguments match `<LivePriceQuote>` props in Task 7.
- `ProductDetailPanel` -> `ApparelDetailPanel` / `PrintDetailPanel` props are all `{ product: Product }` everywhere they are referenced.
- `groupOptionsBySection` returns `Record<SectionName, ProductOption[]>` in Task 3 and is consumed with the same shape in Task 6.
- Decimal values from the backend (Pydantic `Decimal`) are typed as `string` (`VariantPriceTier.price`, `PriceQuote.unit_price`, etc.) consistently across all tasks.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-29-phase5-frontend-pdp.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration via `superpowers:subagent-driven-development`.

**2. Inline Execution** — execute the tasks in this session via `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?
