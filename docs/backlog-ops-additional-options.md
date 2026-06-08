# Backlog: OPS Apparel Variant Model — `setAdditionalOption` Pattern

**Status:** Open — waiting on Christian's confirmation before implementation
**Discovered:** June 5, 2026
**Effort estimate:** 2–3 days (when unblocked)
**Owner:** TBD (Vidhi proposed)

---

## TL;DR

Our current pipeline uses `setProductSize` to model apparel variants (size + color combinations). Live verification against visualgraphx OPS staging shows **this is the wrong mutation for apparel** — sizes/colors should be `setAdditionalOption` + `setAdditionalOptionAttributes` entries. Rebuilding the variant logic is a 2–3 day change; we need Christian's confirmation that this is the intended model before starting.

---

## Evidence

### Reference product 361 — "Ladies Softball 2-Button"

A correctly-configured apparel product in visualgraphx OPS staging.
Inspected June 5, 2026 via OPS GraphQL.

```
productSize entries:                    1  (placeholder only)
productAdditionalOptions entries:       12

Additional Options breakdown:
  id=8130: title="XS"               type="textmp"
  id=8131: title="S"                type="textmp"
  id=8132: title="M"                type="textmp"
  id=8133: title="L"                type="textmp"
  id=8134: title="XL"               type="textmp"
  id=8135: title="2XL"              type="textmp"
  id=8136: title="3XL"              type="textmp"
  id=8137: title="4XL"              type="textmp"
  id=8138: title="5XL"              type="textmp"
  id=8139: title="Material"         type="combo"
  id=8140: title="Measurement"      type="combo"
  id=8141: title="Tall Body Length" type="combo"
```

### Our pushed products (542–545)

```
productSize entries:                    3–8 per product (size_title "Black / OSFA" etc.)
productAdditionalOptions entries:       0  ← THE GAP
```

Our products land in OPS with variant data attached, but **not in the
customer-facing options section**. A customer browsing the storefront
would see raw size rows from a sheet-dimension table, not the proper
"Pick a size" / "Pick a color" dropdowns the reference product uses.

---

## Why this matters

OPS treats apparel differently from print products:

| Pattern | Used for | Visible to customer as |
|---|---|---|
| `setProductSize` | Physical print dimensions (sign sizes "24x36", sheet sizes) | Sheet-size picker |
| `setAdditionalOption` + `setAdditionalOptionAttributes` | Apparel size/color/material | Customer-facing option dropdowns |

We've been using `setProductSize` because the GraphQL mutation name matched
what we thought we needed. The actual model OPS expects for apparel is
Additional Options.

**Customer-facing impact:** Without proper Additional Options, the storefront
won't render correct size/color pickers. Products are technically in OPS
but not "shoppable" in the expected apparel UX.

---

## Christian's confirmation needed

Before starting the rebuild, ask Christian:

1. **For Sport-Tek / Port & Co tees, should apparel sizes go through `setAdditionalOption` + `setAdditionalOptionAttributes`** (like reference product 361)?

2. **What's the right `options_type`?**
   - Reference uses `textmp` for size values (XS, S, M…)
   - Reference uses `combo` for Material, Measurement, Tall Body Length
   - When do you use one vs the other?

3. **For per-variant pricing, do we use `setProductsAttributePrice`** (price per attribute combination)?
   - Our current model has 1 price per size_id
   - Additional Options model needs 1 price per (Size attribute × Color attribute) combination

4. **Migration path for existing products (542–545)?**
   - Delete and re-push?
   - Update existing products with new options?

---

## Proposed scope when unblocked

### Phase 8.1 — payload_builder rewrite (1.5 days)
- Detect apparel products vs print products (`product.product_type == "apparel"`?)
- For apparel: emit `setAdditionalOption("Size")` + N × `setAdditionalOptionAttributes(XS, S, M…)` + same for Color
- Replace `setProductPrice` per variant with `setProductsAttributePrice` per attribute combination
- Drop `setProductSize` from apparel plans (keep for print)

### Phase 8.2 — gateway updates (0.5 day)
- New placeholders for option_id / attribute_id threading
- Handle pricing across attribute combinations (one price row per Size×Color pair)

### Phase 8.3 — tests (0.5 day)
- Mock product with size + color → assert correct setAdditionalOption calls
- End-to-end live verification against visualgraphx

### Phase 8.4 — cleanup (0.5 day)
- Delete misconfigured products (542–545) from OPS staging
- Re-push using new model
- Compare against reference product 361's structure

**Total: 2.5–3 days when unblocked.**

---

## What's already in place

- `setAdditionalOption` and `setAdditionalOptionAttributes` mutation wrappers exist in `modules/ops_client/mutations.py` (committed, tested)
- `setProductsAttributePrice` wrapper exists
- `_build_setAdditionalOption_step` and `_build_setAdditionalOptionAttributes_step` exist in `payload_builder.py` (for `product_local_option_create` strategy)
- They're just **not called** by the apparel push path today

The plumbing is half-built. The work is wiring it into the main payload builder for apparel.

---

## Related findings (same investigation)

- `predefined_product_type` is an enum-like string (e.g. `ap-polos`, `ap-t-shirts`, `ap-hoodies-sweatshirts`), not a number. We send `"1"` as a placeholder; should map SanMar product categories to real OPS templates. Tracked separately — same Christian question.
- The `predefined_product_type` value likely controls which Additional Options OPS auto-suggests in admin UI (a polo template prompts size + color, etc.).

---

## Decision log

- **2026-06-05:** Discovered while investigating why our pushed products (540, 542–545) look different from visualgraphx's existing apparel products. Reference: product 361.
- **2026-06-05:** Decided to ask Christian before rebuilding. Other Phase 5 (retry safety) work proceeds in parallel.
- **TBD:** Christian's reply received.
- **TBD:** Implementation start.
