# Task 15 — 4Over Normalizer

A "normalizer" in API-HUB takes whatever shape a supplier's API returns and reshapes it into the canonical `PSProductData` format the rest of the platform understands. This task builds the normalizer for 4Over, the print-on-demand supplier. It is the second half of the 4Over integration (the first half, Task 14, fetches the raw data; this task turns that raw data into something the database layer can store).

Last updated: 2026-04-20

---

## Files Created / Modified

| File | Change | Purpose |
|------|--------|---------|
| `backend/modules/rest_connector/fourover_normalizer.py` | NEW | The `normalize_4over(...)` function — pure, offline, no DB session |
| `backend/modules/promostandards/schemas.py` | +1 field | `PSProductPart.attributes: dict[str, str] = {}` — holds 4Over's print-specific variant axes (coating, paper weight, finish). Backward-compatible. |
| `backend/test_fourover_normalizer.py` | NEW | 7 offline unit tests, standalone script |

**Commit:** `44033bb` on branch `Vidhi`

---

## Why This Task Exists

API-HUB is a normalize-and-merge platform. Four different suppliers speak four different API dialects, but the database only knows one shape — `PSProductData`, `PSProductPart`, `PSInventoryLevel`, `PSPricePoint`, `PSMediaItem`. Every supplier adapter is responsible for converting its raw response into those canonical shapes. Once data is in canonical form, the same upsert logic (Tanishq's Task 4) handles every supplier identically.

4Over is trickier than the others. SanMar, Alphabroder, and S&S all sell apparel — their variants are naturally described by color and size. 4Over sells print products — brochures, business cards, posters — whose variants are described by paper type, coating, fold, finish, paper weight, and other axes that don't fit into color/size.

Two design problems to solve:

1. **Field names are supplier-specific.** 4Over might call the product name field `productName` or `printProductTitle` or whatever — we don't know until Christian shares the sandbox. We don't want to hardcode anything.
2. **There are more variant axes than color + size.** The canonical schema was built for apparel. 4Over needs somewhere to put coating, paper weight, fold, etc.

**The solution:**

1. For field-name variability, we reuse the Field Mapping UI Vidhi built in V0 Task 16. The user visually pairs each 4Over field with a canonical field (e.g. `productName → product_name`). The mapping is saved to the database as JSON. The normalizer reads that mapping at runtime.
2. For the extra variant axes, we extend `PSProductPart` with an optional `attributes: dict[str, str]` field. Any variant key that the user hasn't explicitly mapped to color or size gets stored there. Nothing is silently dropped.

---

## Plain-English Section for Your Manager

> "Different suppliers send us data in different shapes. SanMar sends fields called 'productName' and 'partId'. 4Over might send 'productTitle' and 'uuid'. Our database only knows one standard shape, so every supplier needs a translator.
>
> I built the translator for 4Over. It reads a configuration that tells it which supplier field matches which database field — that configuration is set by the team through the Field Mapping page I built earlier. 4Over products have extra details like paper type and coating that don't match our standard apparel fields, so the translator preserves those in a general-purpose 'attributes' holder so nothing is lost.
>
> I wrote 7 automated tests covering the main happy path, the unusual cases, and a regression check that my change didn't break our existing SanMar code. All 7 tests pass. The existing 9 tests from last week still pass too."

---

## How Data Flows

```
┌──────────────────┐
│   4Over API      │
│  (REST + HMAC)   │
└────────┬─────────┘
         │  raw JSON
         ▼
┌─────────────────────────┐
│  FourOverClient         │       Task 14
│  get_products()         │       (already shipped)
└────────┬────────────────┘
         │  [{"productName": "Tri-Fold", "uuid": "abc", ...}, ...]
         ▼
┌─────────────────────────┐
│  normalize_4over(...)   │       Task 15 — THIS TASK
│                         │
│  reads                  │
│  supplier.field_mappings│◀──── Field Mapping UI (V0 Task 16)
│    ["mapping"]          │       stores: {"productName": "product_name", ...}
└────────┬────────────────┘
         │  [PSProductData(product_id="abc", product_name="Tri-Fold", ...), ...]
         ▼
┌─────────────────────────┐
│  upsert_products(...)   │       Task 4 (Tanishq)
│  PostgreSQL ON CONFLICT │
└────────┬────────────────┘
         │
         ▼
   products / product_variants / product_images tables
         │
         ▼
   n8n OPS Push Workflow → OnPrintShop storefront
```

**Task 15 is the translation layer.** Before this, 4Over data had nowhere to go. Now it speaks the same language as SanMar and S&S.

---

## The Function Contract

```python
from modules.rest_connector.fourover_normalizer import normalize_4over

products: list[PSProductData] = normalize_4over(
    raw_products,     # list[dict] — from FourOverClient.get_products()
    field_mapping,    # dict[str, str] — from supplier.field_mappings["mapping"]
    variants_key="variants",  # override if 4Over uses a different key
)
```

**Input: `raw_products`** — a list of dicts exactly as 4Over returns them.

**Input: `field_mapping`** — a `{source_field: canonical_field}` dict where source keys are 4Over's field names and targets are one of the 11 canonical names the UI supports.

**Output: `list[PSProductData]`** — ready for Tanishq's `upsert_products()`.

**Edge behaviour:**
- Products missing a mapped `supplier_sku` are skipped silently (malformed records don't abort the whole batch).
- Variants missing a `partId`/`id`/`uuid` still get created — they just get `part_id=""`.
- Empty input returns an empty list, not an error.
- Wrong types raise `TypeError` immediately with a clear message.

---

## The 11 Canonical Fields the UI Exposes

Must match the `CANONICAL_FIELDS` array in `frontend/src/app/mappings/[supplierId]/page.tsx`.

| Canonical | Goes Into | Level |
|-----------|-----------|-------|
| `product_name` | `PSProductData.product_name` | Product |
| `supplier_sku` | `PSProductData.product_id` | Product |
| `brand` | `PSProductData.brand` | Product |
| `description` | `PSProductData.description` | Product |
| `product_type` | `PSProductData.product_type` + `categories[0]` | Product |
| `image_url` | `PSProductData.primary_image_url` | Product |
| `color` | `PSProductPart.color_name` | Variant |
| `size` | `PSProductPart.size_name` | Variant |
| `base_price` | *(Not stored on PSProductData — used elsewhere by pricing sync)* | — |
| `inventory` | *(Not stored — 4Over is print-on-demand)* | — |
| `warehouse` | *(Not stored — 4Over has no warehouse concept)* | — |

**Note:** `base_price`, `inventory`, and `warehouse` are canonical fields the UI exposes, but 4Over specifically doesn't need them — print-on-demand products are quoted live (via `FourOverClient.get_quote`) and aren't held in warehouses. The UI still shows these fields so the same mapping page works for S&S (which does use them).

---

## The `attributes` Field — How Extra Data Survives

A 4Over variant might look like:

```json
{
  "partId": "brochure-001-glossy-uv-tri",
  "paperType": "Glossy",
  "coating": "UV",
  "fold": "Tri",
  "paper_weight": "100gsm",
  "finish": "matte"
}
```

Suppose the user's mapping pairs `paperType → color` and `fold → size`. The other three (`coating`, `paper_weight`, `finish`) aren't in the mapping. Rather than dropping them, the normalizer packs them into the variant's `attributes`:

```python
PSProductPart(
    part_id="brochure-001-glossy-uv-tri",
    color_name="Glossy",      # mapped from paperType
    size_name="Tri",          # mapped from fold
    attributes={
        "coating": "UV",
        "paper_weight": "100gsm",
        "finish": "matte",
    }
)
```

This means we can add a column later to persist these, or surface them in the OPS product config UI (Task 23), or search on them — all without changing the normalizer.

---

## Why We Extended `PSProductPart` Instead of Using `description`

Two options were on the table:

| Option | Pros | Cons |
|--------|------|------|
| Pack into `description` as `"Coating: UV, Paper: 100gsm"` | No schema change | Mixes human-readable text and machine-readable data — can't round-trip or query |
| Add `attributes: dict[str, str] = {}` | Structured, queryable, can be persisted later | Touches Sinchana's Task 2 schema file |

We chose the structured option. The extension is backward-compatible — SanMar's SOAP normalizer just doesn't set `attributes` and the field defaults to an empty dict. All 9 Task 14 tests and the SanMar codepath continue to pass (verified via `test_attributes_default_for_sanmar_part`).

---

## Algorithm — What the Normalizer Actually Does

Per raw product:

1. **Validate** — if it's not a dict, skip it.
2. **Apply top-level mapping** — iterate the `field_mapping` dict; for each `source → canonical` pair, if the raw product has `source`, store its value under `canonical`. Result is a dict keyed by canonical names.
3. **Guard against missing SKU** — if no `supplier_sku` was produced, skip the product.
4. **Normalize each variant:**
   a. Apply the same mapping to the variant dict.
   b. Pick `part_id` from (in order): explicit `supplier_sku` in the mapping, fallback to `partId`/`id`/`uuid` on the raw variant.
   c. Collect every other variant field that wasn't part of the mapping into `attributes`.
5. **Construct `PSProductData`** with the canonical fields + the list of parts.
6. **Default `product_type`** to `"print"` if not mapped (so downstream code can tell 4Over products apart from apparel).

Total: ~60 lines of actual logic, no external dependencies beyond the schemas module.

---

## Test Coverage

All 7 tests in `backend/test_fourover_normalizer.py` pass. Breakdown:

| # | Test | What it proves |
|---|------|---------------|
| 1 | `test_happy_path_three_products` | 3 realistic 4Over products with a full mapping produce 3 correct `PSProductData` with populated variants |
| 2 | `test_variant_attributes_packed` | A variant with 5 fields — 2 mapped, 3 not — ends up with color/size filled AND the unmapped 3 in `attributes` |
| 3 | `test_missing_supplier_sku_skipped` | A malformed product without a SKU is skipped; the two valid products are still returned |
| 4 | `test_empty_mapping_returns_empty_fields` | With only `uuid → supplier_sku` and `productName → product_name` mapped, the other canonical fields default to `None` |
| 5 | `test_empty_input` | `normalize_4over([], {...})` returns `[]` without error |
| 6 | `test_attributes_default_for_sanmar_part` | Regression guard: `PSProductPart(part_id="x")` still constructs with empty `attributes`, confirming Sinchana's SOAP normalizer continues to work |
| 7 | `test_type_validation` | Wrong input types raise `TypeError` with a clear message, not `AttributeError` |

Regression check — all 9 Task 14 client tests still pass after the schema extension.

---

## How to Test

```bash
cd /Users/PD/API-HUB/backend
source .venv/bin/activate
python test_fourover_normalizer.py
```

Expected:

```
Running FourOver normalizer tests…

  test_happy_path_three_products OK
  test_variant_attributes_packed OK
  test_missing_supplier_sku_skipped OK
  test_empty_mapping_returns_empty_fields OK
  test_empty_input OK
  test_attributes_default_for_sanmar_part OK
  test_type_validation OK

All 7 tests passed ✅
```

Also verify Task 14 is unaffected:

```bash
python test_fourover_client.py   # expected: All 9 tests passed ✅
```

### Interactive sanity check

Want to see the normalizer in action with your own input? Run this:

```bash
python -c "
from modules.rest_connector.fourover_normalizer import normalize_4over

raw = [{
    'uuid': 'demo-1',
    'productName': 'Demo Brochure',
    'productBrand': '4Over',
    'variants': [
        {'partId': 'demo-1-glossy-uv', 'paperType': 'Glossy', 'coating': 'UV'},
    ],
}]

mapping = {
    'uuid': 'supplier_sku',
    'productName': 'product_name',
    'productBrand': 'brand',
    'paperType': 'color',
}

result = normalize_4over(raw, mapping)
p = result[0]
print(f'product_id:       {p.product_id}')
print(f'product_name:     {p.product_name}')
print(f'brand:            {p.brand}')
print(f'part[0].part_id:  {p.parts[0].part_id}')
print(f'part[0].color:    {p.parts[0].color_name}')
print(f'part[0].attributes: {p.parts[0].attributes}')
"
```

Expected output:

```
product_id:       demo-1
product_name:     Demo Brochure
brand:            4Over
part[0].part_id:  demo-1-glossy-uv
part[0].color:    Glossy
part[0].attributes: {'coating': 'UV'}
```

Notice `coating` survived into `attributes` even though we didn't map it.

---

## How It Connects to the Rest of the System

```
Field Mapping UI (V0 Task 16 — Vidhi)
       │  PUT /api/suppliers/{id}/mappings
       ▼
Supplier.field_mappings  (JSONB column on suppliers table)
       │
       │  {"mapping": {"productName": "product_name", ...}}
       │
       └────▶ normalize_4over(raw_products, mapping["mapping"])  ◀── Task 15 (THIS)
                     │
                     │  list[PSProductData]
                     ▼
              upsert_products()  (Task 4 — Tanishq)
                     │
                     ▼
              products / product_variants tables
```

**Task 16 (Urvashi)** will add a `rest_hmac` branch to the sync endpoint that chains `FourOverClient` → `normalize_4over` → `upsert_products`.

---

## What's Next

- **Task 16 (Urvashi) — Sync route `rest_hmac` branch.** Adds the glue endpoint that calls `FourOverClient.get_products()`, passes the result to `normalize_4over()`, and then to `upsert_products()`. Uses the field mapping stored on the supplier row.
- **E2E test with real 4Over sandbox.** Blocked on Christian's credentials. Once live, confirm that the real shape of 4Over's response matches the `variants_key="variants"` default — if not, it's a one-line change.
- **Optional: persist `PSProductPart.attributes`.** For V1, attributes are normalized in-memory but not yet stored in the DB. If the team wants to surface coating/paper_weight in the OPS product config page (Task 23), we add a column on `product_variants`.

---

## One-Line Summary for Sprint Review

> Task 15 ships the 4Over normalizer: raw JSON → `PSProductData` via the user's saved Field Mapping config, with print-specific attributes preserved in a new backward-compatible `PSProductPart.attributes` dict. 7 unit tests pass; Task 14's 9 tests continue to pass. Ready for Urvashi to wire into the sync route.
