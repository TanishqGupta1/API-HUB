# Sanmar Product UI Tasks A, B, C, D — Detail Guide

**Status:** ✅ Completed on 2026-04-27
**Branch:** `Vidhi`
**What you can say in one sentence:** *"I added price display on product cards, a VG vs Supplier source filter on the catalog, an options summary panel on VG product detail pages, and a collapsible 4-step 'How to Push to OPS' guide — all pure frontend, no new API endpoints needed."*

---

## 1. What Got Built

| Task | File Changed | What Changed |
|---|---|---|
| **A** — Price on cards | `frontend/src/components/products/product-card.tsx` | Added green price range (`$3.99` or `$4.50–$18.00`) to card footer |
| **B** — Source filter | `frontend/src/app/(admin)/products/page.tsx` | Added 3 pill tabs: All Products / ★ VG Products / ↓ Supplier Products |
| **C** — Options on detail | `frontend/src/app/(admin)/products/[id]/page.tsx` | Options summary panel for VG products + source badge at top |
| **D** — Push flow guide | `frontend/src/app/(admin)/products/[id]/page.tsx` | Collapsible "How to Push to OPS" 4-step panel |

No new API endpoints. No backend changes. No new tests required.

---

## 2. Background — What Is This Task About?

The teammate message was:
> *"Check SanMar pricing and Differentiate SanMar and OPS product and display product option for VG products and HOW to push data to OPS"*

This broke into 4 concrete frontend tasks. All required data was already available in existing API responses — nothing new needed from the backend.

---

## 3. Task A — Price Range on Product Cards

### Problem
The product list API already returns `price_min` and `price_max` fields but the product card never displayed them. Users had no idea of pricing without opening each product.

### What Changed
**File:** `frontend/src/components/products/product-card.tsx`

Added to the card footer (right side, next to variant count):
```tsx
{product.price_min != null && (
  <span className="font-mono text-[12px] font-semibold text-[#247a52]">
    {product.price_max != null && product.price_max !== product.price_min
      ? `$${Number(product.price_min).toFixed(2)}–$${Number(product.price_max).toFixed(2)}`
      : `$${Number(product.price_min).toFixed(2)}`}
  </span>
)}
```

### How it looks
- Single price: `$3.99`
- Range: `$4.50–$18.00`
- No price in DB: nothing shown (graceful empty)

### Is it dynamic?
**Yes, fully dynamic.** The price reads directly from `price_min` / `price_max` which the backend calculates from all variant `base_price` values. When real supplier credentials are added and a sync runs, prices update automatically — no frontend change needed.

---

## 4. Task B — VG vs Supplier Source Filter

### Problem
The catalog showed all products (VG-owned and supplier-sourced) mixed together with no way to filter by source. Users couldn't quickly find only their own VG products vs externally sourced products.

### What Changed
**File:** `frontend/src/app/(admin)/products/page.tsx`

Added state:
```tsx
const [sourceFilter, setSourceFilter] = useState<"all" | "vg" | "supplier">("all");
```

Added client-side filter logic:
```tsx
const isVg = (p: ProductListItem) =>
  (p.supplier_name ?? "").toLowerCase().includes("visual graphics");

const displayedProducts = products.filter((p) => {
  if (sourceFilter === "vg") return isVg(p);
  if (sourceFilter === "supplier") return !isVg(p);
  return true;
});
```

Added 3 pill tabs above the search bar:
```
[ All Products ]  [ ★ VG Products ]  [ ↓ Supplier Products ]
```

### How it works
- **All Products** → shows everything
- **★ VG Products** → shows only products where `supplier_name` contains "visual graphics" (VG OPS products)
- **↓ Supplier Products** → shows SanMar, S&S Activewear, 4Over, Alphabroder products

No extra API call — filters the already-loaded products list client-side.

---

## 5. Task C — Product Options Panel on Detail Page

### Problem
VG/OPS products have configurable options (substrate class, print sides, ink type, finish, etc.) stored in the DB via the `/api/products/{id}/options-config` endpoint. Nothing on the product detail page showed these options — users had to know to navigate to a separate `/options` URL.

### What Changed
**File:** `frontend/src/app/(admin)/products/[id]/page.tsx`

1. Added `OptionConfigItem[]` state and fetch on load for `ops_graphql` products:
```tsx
const [options, setOptions] = useState<OptionConfigItem[]>([]);

// Inside fetchData:
if (sup.protocol === "ops_graphql") {
  const opts = await api<OptionConfigItem[]>(`/api/products/${id}/options-config`);
  setOptions(opts);
}
```

2. Replaced the yellow alert banner at the top with a clean **source badge**:
- VG products: `★ VG PRODUCT — owned by Visual Graphics OPS` (blue pill)
- Supplier products: `↓ SUPPLIER PRODUCT — sourced from SanMar Corporation` (grey pill)

3. Added **Options panel** below the variants table (VG products only):
- If options exist → shows grid of option cards (name, enabled/disabled toggle, active attribute count) + link to full configure page
- If empty → shows empty state with explanation and button to open `/products/{id}/options`
- "Manage Options (N)" button links directly to the full options configuration page

### How it looks when empty (demo data)
```
⚙️  No options configured yet
Options control what customers can choose when ordering —
substrate, print sides, ink type, finish, etc.

[ Open Options Configuration ]
```

### How it looks when options exist (after OPS sync)
Grid of cards showing each option (Substrate Class, Print Sides, Ink Type etc.)
with green "On" / grey "Off" toggle state and attribute count.

### Where the full options config page is
`http://localhost:3000/products/{id}/options`

This page matches the OPS "Assign Product Options" layout exactly — 3-column grid of option cards, each with:
- Toggle (enabled/disabled)
- Attribute checkboxes with price + sort order fields
- Save per card + Save All
- Search and tag filter

---

## 6. Task D — How to Push to OPS Guide

### Problem
The "Publish to OPS" button existed but users had no idea what happened when they clicked it — what systems were involved, what OPS GraphQL calls were made, or what the push log meant.

### What Changed
**File:** `frontend/src/app/(admin)/products/[id]/page.tsx`

Added a collapsible panel between the Options panel and Push History:

```
HOW TO PUSH TO OPS                              ▼ expand
```

When expanded, shows 4 steps in cards:

| Step | Icon | Title | Description |
|---|---|---|---|
| 1 | 📦 | Product data fetched | Hub pulls name, variants, images, pricing from supplier API |
| 2 | 💲 | Markup applied | Markup rules calculate final customer-facing price from base_price |
| 3 | 🚀 | n8n sends to OPS | Workflow calls OPS GraphQL: setProduct → setProductSize → setProductPrice → setProductImage |
| 4 | ✅ | Push logged | OPS product ID saved here. Re-pushing updates instead of creating a duplicate |

Plus a blue info box:
> **To push this product:** click Publish to OPS above → select a customer/storefront → confirm. The job runs in the background via n8n. Check push history below for status.

### Is this the actual flow?
Yes. This matches the real n8n workflow in `n8n-workflows/ops-push.json` and the backend at `backend/modules/push_log/routes.py`.

---

## 7. Verification Checklist

### Task A
- [ ] Go to `http://localhost:3000/products`
- [ ] Product cards show green price (`$3.99`, `$8.50`, etc.) in the footer
- [ ] If variant prices differ, shows range (`$4.50–$18.00`)

### Task B
- [ ] 3 pill tabs visible above search bar: All / ★ VG Products / ↓ Supplier Products
- [ ] Clicking **★ VG Products** → shows only VG products (Performance Tech Hoodie, Custom Branded Pen)
- [ ] Clicking **↓ Supplier Products** → shows SanMar, S&S, etc.
- [ ] Result count updates with each filter

### Task C
- [ ] Go to `http://localhost:3000/products/1bb65ced-9ff8-445e-bcc7-69b65c8388e6`
- [ ] Blue **★ VG PRODUCT** badge at the top of the page
- [ ] **Product Options** panel visible below the variants table
- [ ] "No options configured yet" empty state with button to configure
- [ ] For a SanMar product: grey **↓ SUPPLIER PRODUCT** badge, no Options panel

### Task D
- [ ] Same VG product detail page
- [ ] **HOW TO PUSH TO OPS** collapsible panel visible below Options panel
- [ ] Click to expand → 4 step cards appear (📦 → 💲 → 🚀 → ✅)
- [ ] Blue info box explains how to trigger the push

---

## 8. Files & Lines to Reference

| File | What |
|---|---|
| `frontend/src/components/products/product-card.tsx` | Task A — price range in footer |
| `frontend/src/app/(admin)/products/page.tsx` | Task B — source filter tabs + `displayedProducts` |
| `frontend/src/app/(admin)/products/[id]/page.tsx` | Task C + D — source badge, options panel, push guide |
| `frontend/src/app/(admin)/products/[id]/options/page.tsx` | Options config page (already existed, unchanged) |
| `frontend/src/components/options/option-card.tsx` | Option card component (already existed, unchanged) |
| `frontend/src/components/options/attribute-row.tsx` | Attribute row with price + sort (already existed, unchanged) |

---

## 9. Why No Backend Changes Were Needed

| Data | Already in API? |
|---|---|
| `price_min`, `price_max` | ✅ Already returned by `GET /api/products` |
| `supplier_name` | ✅ Already in every `ProductListItem` |
| `GET /api/products/{id}/options-config` | ✅ Already existed, returns `[]` until OPS connected |
| Push log, customers list | ✅ Already in `GET /api/push-log` and `GET /api/customers` |

All 4 tasks were pure frontend reads of data already available.
