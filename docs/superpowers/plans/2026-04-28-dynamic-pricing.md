# Dynamic Pricing on Product Detail Page

**Goal:** When a customer selects customization options (Print Sides, Ink Type, Material, etc.) on the storefront PDP, the displayed price updates in real time to reflect the price modifiers configured by the admin.

**Architecture:** Three-layer data flow:
1. Admin sets per-attribute price modifiers at `/products/[id]/options` (already exists — `OptionConfigItem[].attributes[].price`)
2. PDP fetches those modifiers + builds a lookup map, then tracks the running adjustment as the user picks options
3. `PriceBlock` shows `base_price + option_adjustment` live

**No schema changes.** All the data already exists. This is purely frontend wiring.

**Files touched:** 3 frontend files, no backend changes.

```
frontend/src/app/storefront/vg/product/[product_id]/page.tsx   ← fetch options-config + wire adjustment state
frontend/src/components/storefront/product-options.tsx          ← accept priceLookup, compute + emit adjustment, show +$X.XX hints
frontend/src/components/storefront/price-block.tsx              ← accept optional adjustment prop
```

**Join key:**
`ProductOptionAttribute.ops_attribute_id` (number | null) === `AttributeConfigItem.ops_attribute_id` (int)

---

## Task 1: Extend `PriceBlock` to accept a price adjustment

**File:** `frontend/src/components/storefront/price-block.tsx`

**Why:** Currently `PriceBlock` shows only `variant.base_price`. We need it to show `base_price + option_adjustment` when options are selected. Adding an optional `adjustment` prop keeps the component backwards-compatible everywhere it is used.

- [ ] **Step 1: Add `adjustment` prop**

Change the `PriceBlockProps` interface from:
```typescript
interface PriceBlockProps {
  variant: Variant | null;
  fallback?: Variant[];
}
```
to:
```typescript
interface PriceBlockProps {
  variant: Variant | null;
  fallback?: Variant[];
  adjustment?: number;
}
```

- [ ] **Step 2: Use `adjustment` in the variant price display**

In the variant branch replace:
```typescript
export function PriceBlock({ variant, fallback = [] }: PriceBlockProps) {
```
with:
```typescript
export function PriceBlock({ variant, fallback = [], adjustment = 0 }: PriceBlockProps) {
```

And replace:
```typescript
      <div className="font-mono text-[28px] font-extrabold text-[#1e4d92] leading-none">
          {fmt(variant.base_price)}
        </div>
```
with:
```typescript
      <div className="font-mono text-[28px] font-extrabold text-[#1e4d92] leading-none">
          {fmt((variant.base_price ?? 0) + adjustment)}
        </div>
        {adjustment !== 0 && (
          <div className="text-[11px] font-mono text-[#484852]">
            Base {fmt(variant.base_price)}
            <span className={adjustment > 0 ? "text-[#1e7a3c] ml-1" : "text-[#b93232] ml-1"}>
              {adjustment > 0 ? `+${fmt(adjustment)}` : fmt(adjustment)} options
            </span>
          </div>
        )}
```

- [ ] **Step 3: Verify no TypeScript errors**

Run: `cd frontend && npm run lint`
Expected: PASS, no new errors.

---

## Task 2: Add price-awareness to `ProductOptions`

**File:** `frontend/src/components/storefront/product-options.tsx`

**Why:** `ProductOptions` currently tracks `picked` (which attribute is selected per option group) but never does anything with it. We need it to:
1. Accept a `priceLookup` map (`ops_attribute_id → price modifier`)
2. Recompute the total adjustment whenever `picked` changes and emit it via `onPriceChange`
3. Show a small `+$X.XX` / `-$X.XX` hint next to each attribute so the user knows what they're adding

- [ ] **Step 1: Update the component signature**

Change:
```typescript
export function ProductOptions({ options }: { options: ProductOption[] | undefined | null }) {
```
to:
```typescript
interface ProductOptionsProps {
  options: ProductOption[] | undefined | null;
  priceLookup?: Map<number, number>;
  onPriceChange?: (adjustment: number) => void;
}

export function ProductOptions({ options, priceLookup, onPriceChange }: ProductOptionsProps) {
```

- [ ] **Step 2: Emit price adjustment whenever `picked` changes**

Add a `useEffect` after the existing `useState` for `picked`:
```typescript
useEffect(() => {
  if (!priceLookup || !onPriceChange) return;
  let total = 0;
  visible.forEach((opt) => {
    const attr = opt.attributes.find((a) => a.id === picked[opt.id]);
    if (attr?.ops_attribute_id != null) {
      total += priceLookup.get(attr.ops_attribute_id) ?? 0;
    }
  });
  onPriceChange(total);
}, [picked, visible, priceLookup, onPriceChange]);
```

- [ ] **Step 3: Show price hint on each attribute**

In the radio button render, change:
```typescript
                      <button
                        key={a.id}
                        type="button"
                        onClick={() => setPicked((p) => ({ ...p, [opt.id]: a.id }))}
                        className={
                          "px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors " +
                          (active
                            ? "border-[#1e4d92] bg-[#1e4d92] text-white"
                            : "border-[#e9e7e3] bg-[#f9f7f4] text-[#484852] hover:border-[#1e4d92] hover:text-[#1e4d92]")
                        }
                      >
                        {a.title}
                      </button>
```
to:
```typescript
                      <button
                        key={a.id}
                        type="button"
                        onClick={() => setPicked((p) => ({ ...p, [opt.id]: a.id }))}
                        className={
                          "px-2.5 py-1 rounded-full text-[11px] font-semibold border transition-colors " +
                          (active
                            ? "border-[#1e4d92] bg-[#1e4d92] text-white"
                            : "border-[#e9e7e3] bg-[#f9f7f4] text-[#484852] hover:border-[#1e4d92] hover:text-[#1e4d92]")
                        }
                      >
                        {a.title}
                        {(() => {
                          const mod = a.ops_attribute_id != null ? priceLookup?.get(a.ops_attribute_id) : undefined;
                          if (!mod) return null;
                          return (
                            <span className={`ml-1 text-[10px] font-mono ${active ? "text-blue-200" : mod > 0 ? "text-[#1e7a3c]" : "text-[#b93232]"}`}>
                              {mod > 0 ? `+$${mod.toFixed(2)}` : `-$${Math.abs(mod).toFixed(2)}`}
                            </span>
                          );
                        })()}
                      </button>
```

In the `<select>` render, change:
```typescript
                  {attrs.map((a) => (
                    <option key={a.id} value={a.id}>
                      {a.title}
                    </option>
                  ))}
```
to:
```typescript
                  {attrs.map((a) => {
                    const mod = a.ops_attribute_id != null ? priceLookup?.get(a.ops_attribute_id) : undefined;
                    return (
                      <option key={a.id} value={a.id}>
                        {a.title}{mod ? (mod > 0 ? ` (+$${mod.toFixed(2)})` : ` (-$${Math.abs(mod).toFixed(2)})`) : ""}
                      </option>
                    );
                  })}
```

- [ ] **Step 4: Verify lint**

Run: `cd frontend && npm run lint`
Expected: PASS.

---

## Task 3: Wire everything together in the PDP page

**File:** `frontend/src/app/storefront/vg/product/[product_id]/page.tsx`

**Why:** The PDP page needs to (a) fetch the options-config for this product, (b) build a `priceLookup` map from it, (c) hold `optionAdj` state, and (d) pass the right props to `ProductOptions` and `PriceBlock`.

- [ ] **Step 1: Add imports**

Add to the import block:
```typescript
import type { OptionConfigItem } from "@/lib/types";
```

- [ ] **Step 2: Add state + fetch**

After the existing `useState` declarations add:
```typescript
const [optionAdj, setOptionAdj] = useState(0);
const [priceLookup, setPriceLookup] = useState<Map<number, number>>(new Map());
```

Inside the `useEffect` that fetches the product, after `setProduct(p)` add:
```typescript
        // Fetch admin-configured price modifiers for each option attribute
        try {
          const configs = await api<OptionConfigItem[]>(`/api/products/${productId}/options-config`);
          const lookup = new Map<number, number>();
          configs.forEach((opt) => {
            opt.attributes.forEach((attr) => {
              if (attr.enabled && Number(attr.price) !== 0) {
                lookup.set(attr.ops_attribute_id, Number(attr.price));
              }
            });
          });
          setPriceLookup(lookup);
        } catch { /* options-config is optional — non-OPS products won't have it */ }
```

- [ ] **Step 3: Pass props to `ProductOptions`**

Change:
```typescript
      <ProductOptions options={product.options} />
```
to:
```typescript
      <ProductOptions
        options={product.options}
        priceLookup={priceLookup}
        onPriceChange={setOptionAdj}
      />
```

- [ ] **Step 4: Pass `adjustment` to `PriceBlock`**

Change:
```typescript
      <PriceBlock variant={selectedVariant} fallback={product.variants} />
```
to:
```typescript
      <PriceBlock variant={selectedVariant} fallback={product.variants} adjustment={optionAdj} />
```

- [ ] **Step 5: Verify TypeScript + lint**

Run: `cd frontend && npm run lint`
Expected: PASS, no new errors.

---

## Task 4: Smoke-test in the browser

**Why:** Dynamic price updates only show correctly when options actually have non-zero price modifiers configured. Verify the full loop works end-to-end.

- [ ] **Step 1: Make sure the frontend is running**

Run: `docker compose up -d frontend`
Expected: frontend starts on `:3000`.

- [ ] **Step 2: Set a price modifier on one attribute via the admin UI**

1. Open `http://localhost:3000/products/ed813af4-8e1c-429b-8044-4291ad4965c8/options` (Performance Tech Hoodie — OPS product)
2. Find any enabled option group (e.g. Print Sides)
3. Set a non-zero price on one attribute (e.g. `Double - Same Art` → `5.00`)
4. Click Save on that card

- [ ] **Step 3: Open the storefront PDP and verify price updates**

Open `http://localhost:3000/storefront/vg/product/ed813af4-8e1c-429b-8044-4291ad4965c8`

Expected behaviour:
- Base price shows normally (e.g. `$12.50`)
- When you switch to `Double - Same Art`, price updates to `$17.50` with a breakdown line showing `Base $12.50 +$5.00 options`
- Switching back to `Single` returns to `$12.50` with no breakdown line
- Dropdown options show `(+$5.00)` hint next to attributes that have a modifier

- [ ] **Step 4: Verify zero-modifier attributes show no hint**

Any attribute with `price = 0` (or not in the lookup) must show no price hint — confirm that.

---

## Task 5: Commit

```bash
git add frontend/src/components/storefront/price-block.tsx \
        frontend/src/components/storefront/product-options.tsx \
        frontend/src/app/storefront/vg/product/[product_id]/page.tsx
git commit -m "feat(storefront): dynamic pricing from option attribute modifiers

Price on the PDP now updates in real time as the customer selects
customization options. Adjustment = sum of admin-configured price
modifiers for the selected attributes. Shows breakdown line (Base +
options) and per-attribute +$/- hints in selectors and radio pills."
```

---

## Self-review checklist

- No backend changes — all data already exists in `/api/products/{id}/options-config`
- Join key verified: `ProductOptionAttribute.ops_attribute_id` === `AttributeConfigItem.ops_attribute_id` (both `number`)
- Backwards-compatible: `PriceBlock` and `ProductOptions` work unchanged where `adjustment`/`priceLookup` are not passed
- Non-OPS products: the `try/catch` in the fetch means SanMar/4Over/S&S PDPs are unaffected
- Only attributes with `enabled: true` AND `price !== 0` enter the lookup — disabled attributes don't affect price
- No new API endpoints needed
