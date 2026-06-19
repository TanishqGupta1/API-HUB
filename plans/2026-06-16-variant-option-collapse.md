# Variant → Option Collapse (Master-Option Shape) — Implementation Plan

**Date:** 2026-06-16
**Scope:** api-hub / GraphX Connect ONLY. No OPS push, no graphx ingest.
**Goal:** Turn the flat per-product variant matrix (color × size rows) into clean
selectable axes — a **Color option** + a **Size option** — so one supplier style
is one product with options, not N products.

> **Revised 2026-06-16 after critic review.** Original plan emitted size *twice*
> (as `product_sizes` rows AND a size option). Dropped the `product_sizes` half:
> `product_sizes` is a **physical width/height** table (NOT NULL `width`/`height`,
> unique on `(product_id, width, height)` — models.py:230,237-238) built for
> print/OPS dimensions, not apparel S/M/L. It cannot represent apparel sizes
> (every row would collapse to one `(product_id, 0, 0)` key) and the planned
> `ON CONFLICT (product_id, size_title)` referenced a non-existent column/index.
> Size is now emitted as a `ProductOption` only — meets the goal with zero schema
> change. Physical size→OPS `setProductSize` is a later graphx/OPS concern,
> out of scope here.

---

## 1. Problem

SanMar (and every PromoStandards apparel supplier) returns a *matrix*: one style
(e.g. PC54 tee) explodes into `colors × sizes` variants. PC54 = 8 colors × 6
sizes = **48 `product_variants` rows**.

Today api-hub stores those 48 rows and nothing else. Downstream (graphx → OPS)
needs the style as **one product** where color and size are *options the buyer
picks*, not 48 separate products. The data to build those option lists already
lives in the variants — it's just never extracted.

**Infrastructure already exists, derivation does not:**
- `ProductIngest.options: list[OptionIngest]` (schemas.py:266) — storage slot.
- `_upsert_options()` (ingest.py:116) — upserts `product_options` by
  `(product_id, option_key)` + delete-reinserts attributes. Idempotent per option.
- `OptionIngest` / `OptionAttributeIngest` / `ProductSizeIngest` schemas exist.
- `ProductOption` / `ProductOptionAttribute` / `ProductSize` models exist.

The gap: **nothing reads `product_variants` and populates `options` / sizes.**
The normalizer (`ps_normalizer_v2`) only emits variants.

---

## 2. Approach (decided)

- **Separate idempotent pass** over *stored* variants — not inline in the
  normalizer, not in the persist write-path. Re-runnable, decoupled from fetch,
  can backfill all 994 existing products, covers SOAP + REST paths uniformly.
- **Variants stay source-of-truth.** They hold SKU / inventory / price needed
  for ordering. The pass only *reads* them and writes derived projections
  alongside. Variants are never mutated.
- **Size as `ProductOption` only** (revised — see banner). Color and size are
  both options; full-replace each run → cannot drift. No `product_sizes` write,
  so no conflict with `persist_product`'s own size handling.

---

## 3. Component

New file: `backend/modules/catalog/option_collapse.py`

### `derive_options(db, product_id) -> CollapseResult`
Pure derivation for one product. Single transaction. Steps:

1. Load the product's `product_variants` (color, size only — ignore price/sku).
2. **Normalize-then-dedup** (critical — raw SanMar values have inconsistent
   casing/trailing space): map each `variant.color` to a normalized display
   `title` (trim, collapse whitespace; keep original casing for display but
   dedup on a casefold key). `distinct_colors` = ordered set keyed on the
   casefold-normalized title; same for `distinct_sizes`. This prevents `"Red"`
   vs `"RED "` from producing two attributes that collide on
   `uq_option_attribute_title` (models.py:154) and abort the txn.
3. Build option payloads:
   - **Color** → `OptionIngest(option_key="color", title="Color",
     options_type="swatch", required=bool(distinct_colors))` with one
     `OptionAttributeIngest(title=color, attribute_key=slug(color),
     sort_order=i)` per distinct color.
   - **Size** → `OptionIngest(option_key="size", title="Size",
     options_type="dropdown", required=bool(distinct_sizes))` with one attribute
     per distinct size. **`required` symmetric with Color** — size is as
     mandatory as color for orderable apparel.
   - OPS-binding fields (`ops_option_id`, `master_option_id`,
     `ops_attribute_id`, `master_attribute_id`) left **null** — graphx/push
     fills them later. Out of scope here.
   - Top-level `sort_order`: Color=0, Size=1 (stable inter-option order).
4. Persist:
   - Reuse `_upsert_options(db, product_id, [color_opt, size_opt])`.
   - **`enabled` gap:** `_upsert_options` sets `status=1` but never sets
     `enabled` (model default `False`, models.py:142). Derived options must be
     visible — set `enabled=True` for derived options (extend `_upsert_options`
     values/set_, or pass through `OptionIngest`). Confirm whether any read path
     filters on `enabled` before deciding; default to `enabled=True`.
   - **Full-replace guard (prune):** after upsert, delete any `product_options`
     for this product whose `option_key` is a *derived* key (`color`,`size`) but
     not in the new set (handles a color/size disappearing between syncs).
     `_upsert_options` today only upserts/refreshes — it does NOT prune removed
     options (ingest.py:116-181, confirmed). Add the prune. Attribute children
     cascade on option delete (FK `ondelete="CASCADE"`, models.py:161).
   - **No `product_sizes` write** (dropped — see banner).
5. Return `CollapseResult(colors=n, sizes=n, color_attrs=n, size_attrs=n)`.

### `derive_options_bulk(db, supplier_id=None) -> dict`
Walk products (all, or one supplier's), call `derive_options` per product,
aggregate counts. Used to backfill the 994 existing products. Commit per product
(or batched) so a single bad product doesn't roll back the run.

### Ordering helpers
- Colors: alphabetical (stable).
- Sizes: canonical apparel order map
  `{"XS":0,"S":1,"M":2,"L":3,"XL":4,"2XL":5,"XXL":5,"3XL":6,"4XL":7,...}`;
  unknown sizes sorted alphabetically *after* known ones. Lives in this module.
- `slug(color)`: lowercase, non-alnum → `-`, collapse repeats (for `attribute_key`).

---

## 4. Entry points

- Function: `derive_options(db, product_id)`.
- Batch: `derive_options_bulk(db, supplier_id=None)`.
- Routes (admin trigger, in `catalog/routes.py`):
  - `POST /api/catalog/products/{id}/derive-options` → one product.
  - `POST /api/catalog/suppliers/{id}/derive-options` → supplier backfill.
- **Not** auto-hooked into sync yet — manual/explicit for now. (Auto-trigger
  after each sync is a later, separate decision.)

---

## 5. Idempotency / safety

- Re-running on the same variants → identical rows. Options upsert by
  `(product_id, option_key)`; attributes delete-reinsert; removed-option prune.
  No duplicates, no drift.
- **No-op safety:** product with no color → skip Color option. No size → skip
  size option. Non-apparel product (no color/size variants) → pass writes
  nothing. **Skip ≠ delete:** if a product that previously had colors loses ALL
  variants of an axis between runs, the prune (step 4) removes the now-empty
  derived option — so stale options don't linger. Never errors on empty.
- No price moved. No variant mutated. No normalizer change. No `product_sizes`
  touched.

---

## 6. Tests (`backend/tests/test_option_collapse.py`)

1. **Matrix collapse:** 48 variants (8 colors × 6 sizes) → 1 `color` option w/ 8
   attrs, 1 `size` option w/ 6 attrs. No `product_sizes` rows written.
2. **Idempotency:** run twice → identical counts; option/attr rows stable by
   natural key.
3. **No-op:** variants with no color/size → zero derived rows, no error.
4. **Removed value prune:** run with 8 colors, then re-run with 6 (2 removed) →
   color option has 6 attrs, 2 gone. Also: axis emptied entirely → option pruned.
5. **Size ordering:** `2XL` sorts after `XL`, not after `1`/lexical.
6. **Normalize-then-dedup:** variants `"Red"`, `"RED "`, `"red"` → ONE color
   attribute, no `uq_option_attribute_title` violation.
7. **Mixed nulls:** product with some variants color+null-size, others
   null-color+size → both options built correctly from the non-null subsets.
8. **enabled/status:** derived options assert `enabled=True`, `status=1`.
9. **Edge:** single color, single size, color-only (no sizes), size-only.

Use the existing test DB fixture pattern (mirror `test_sanmar_*`).

---

## 7. Out of scope (scope guard)

- No OPS push, no `setMasterOption`/`setAssignOptions`, no OPS-side master-option
  creation.
- No graphx catalog ingest / handoff contract.
- No price migration — price stays on variants.
- No normalizer edits.
- No multi-tenant / per-customer option overrides.

---

## 8. Build order

1. `option_collapse.py` — normalize/slug/size-order helpers + `derive_options`
   (Color first, then Size option).
2. Extend `_upsert_options` (or wrapper): set `enabled=True` + add option-prune
   for removed derived keys.
3. `derive_options_bulk`.
4. Routes (`catalog/routes.py` — read-side router, NOT the `/api/ingest`
   secret-gated write router).
5. Tests (all 9).
6. Backfill run against the 994 existing products (manual, after review).
