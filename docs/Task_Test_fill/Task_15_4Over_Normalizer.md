# Task 15 — 4Over Normalizer — Test Guide & Presentation Script

**Status:** ✅ All 7 tests passed on 2026-04-20
**What you can say in one sentence:** *"I built the translator that converts raw 4Over product data into our platform's standard format. 7 automated tests — all pass."*

---

## 1. What Got Built

| File | Purpose |
|------|---------|
| `backend/modules/rest_connector/fourover_normalizer.py` | The `normalize_4over(...)` function — pure Python, no DB, no network |
| `backend/modules/promostandards/schemas.py` | Extended `PSProductPart` with an optional `attributes` dict (backward-compatible) |
| `backend/test_fourover_normalizer.py` | 7 unit tests |

**Commit:** `44033bb` on branch `Vidhi` — pushed to GitHub

---

## 2. What a "Normalizer" Is — One-Minute Explainer

Every supplier sends product data in their own shape. SanMar calls a field `productName`, 4Over might call it `productTitle`. Our database only understands one shape — so every supplier needs a translator.

**The analogy to use with your manager:**

> "Imagine four suppliers each send their product catalog in a different language — English, French, German, and Japanese. Our database only reads English. A 'normalizer' is the translator for one supplier. This task is the translator for 4Over.
>
> The team configures which 4Over field matches which database field using the Field Mapping page I built earlier. The normalizer reads that configuration and does the translation at run time. It also has a special slot for 4Over's print-specific details like paper type and coating so none of that information is lost."

---

## 3. Test Commands You Run

### Command 1 — full test suite

```bash
cd "$(git rev-parse --show-toplevel)/backend" && source .venv/bin/activate
python test_fourover_normalizer.py
```

### Expected Output

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

### Command 2 — regression check that Task 14 still works

```bash
python test_fourover_client.py
```

### Expected Output

```
Running FourOverClient tests…

  test_sign_header_format OK — sig=36a814917417ea19…
  ... (7 more) ...
  test_http_error_propagates OK

All 9 tests passed ✅
```

**Why this matters:** Task 15 added a new field to a schema that Task 14 uses. The 9 regression tests prove the old code still works — nothing broke.

### Command 3 — live interactive demo

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
print(f'product_id:          {p.product_id}')
print(f'product_name:        {p.product_name}')
print(f'brand:               {p.brand}')
print(f'part[0].part_id:     {p.parts[0].part_id}')
print(f'part[0].color:       {p.parts[0].color_name}')
print(f'part[0].attributes:  {p.parts[0].attributes}')
"
```

### Expected Output

```
product_id:          demo-1
product_name:        Demo Brochure
brand:               4Over
part[0].part_id:     demo-1-glossy-uv
part[0].color:       Glossy
part[0].attributes:  {'coating': 'UV'}
```

**Key talking point:** Notice that `coating` was NOT in the mapping, but the normalizer still captured it in `attributes` so it survives. This is the "nothing gets lost" guarantee.

---

## 4. What Each Test Proves (Plain English)

| # | Test | Plain English | Why It Matters |
|---|------|---------------|----------------|
| 1 | `test_happy_path_three_products` | Given 3 sample 4Over products with a realistic mapping, the normalizer returns 3 correct `PSProductData` objects with populated fields and variants | Confirms the core function works on realistic data |
| 2 | `test_variant_attributes_packed` | A variant with 5 fields where only 2 are mapped — the other 3 end up in the `attributes` dict | Proves our "nothing gets lost" promise |
| 3 | `test_missing_supplier_sku_skipped` | A malformed product with no SKU is skipped silently; valid products around it are still returned | One bad record can't abort a 5000-product sync |
| 4 | `test_empty_mapping_returns_empty_fields` | With a minimal mapping, unmapped canonical fields default to `None` (not an error) | The function is forgiving — partial mappings still work |
| 5 | `test_empty_input` | `normalize_4over([], ...)` returns `[]` | No crash on empty inputs |
| 6 | `test_attributes_default_for_sanmar_part` | `PSProductPart(part_id="x")` still works with no `attributes` kwarg | Regression guard — proves Sinchana's SanMar code isn't broken by our schema change |
| 7 | `test_type_validation` | Passing a string or `None` as the input raises `TypeError` with a clear message | Developers get a useful error, not a cryptic `AttributeError` |

---

## 5. What To Say — Scripted Talking Points

### For your manager (non-technical)

> "4Over sends their product data in their own format — different field names, extra details for print products like paper type and coating. Our platform's database only knows one format, so I built the translator. It uses the configuration the team sets through the Field Mapping page I built earlier, so when 4Over's API changes a field name, we don't change any code — we just update the mapping on screen.
>
> I wrote 7 automated tests. All 7 pass. I also ran the 9 existing tests from last week to confirm nothing I changed broke the existing code — all 9 still pass. Sprint is now complete; six for six."

### For your senior / tech lead

> "Task 15 is `normalize_4over` in `backend/modules/rest_connector/fourover_normalizer.py`. It's a pure function — no DB session, no HTTP — so it's fully unit-testable offline.
>
> It reads the `{source_field: canonical_field}` dict from `supplier.field_mappings['mapping']` and applies it at both the product and variant levels. 4Over has more variant axes than our apparel-centric schema allows, so I extended `PSProductPart` with an optional `attributes: dict[str, str] = {}`. SanMar's SOAP codepath never sets it, so it's fully backward-compatible — and I added a regression test to prove that.
>
> Malformed products without a mapped `supplier_sku` are skipped silently instead of raising, so one bad record can't abort a 5000-product sync. Urvashi's Task 16 will chain `FourOverClient` → `normalize_4over` → `upsert_products` in the sync route. I'm ready for handoff."

### For teammates in standup

> "Task 15 done. 4Over normalizer + schema extension. 7 new tests + 9 regression tests all pass. Pushed to `Vidhi`. My sprint is complete — 6 of 6 tasks shipped."

---

## 6. Likely Questions + Prepared Answers

### Q: "Why did you modify Sinchana's schema file?"

**A:** *"I added one optional field — `attributes: dict[str, str] = {}` — to `PSProductPart`. It defaults to an empty dict, so Sinchana's SanMar normalizer behaviour is completely unchanged. I wrote a regression test (test #6) that constructs a `PSProductPart` the way Sinchana's SOAP normalizer would and confirms it still works. All 9 Task 14 tests still pass too."*

### Q: "What happens if the field mapping is missing?"

**A:** *"The function still runs — it just produces `PSProductData` with mostly `None` fields. The only hard requirement is that `supplier_sku` gets mapped; if it doesn't, that product is skipped silently so one malformed record can't abort a 5000-product batch. Test #3 and test #4 cover this."*

### Q: "What if 4Over uses a different key name than 'variants'?"

**A:** *"The function takes a `variants_key` keyword argument that defaults to `'variants'`. Once Christian provides the sandbox credentials, we'll confirm the actual shape and change the default if needed — it's a single-line change."*

### Q: "Where does coating and paper weight end up?"

**A:** *"In `PSProductPart.attributes` — a dict keyed by the 4Over field name. Any variant field that's not mapped to color or size gets captured there. Test #2 proves this. The database doesn't persist it yet — we'd add a column if the team decides to surface those details in the OPS product config page."*

### Q: "How do you know the field mapping data flows correctly from the UI?"

**A:** *"The UI PUTs `{mapping: {source: target}}` to `/api/suppliers/{id}/mappings`, which stores the whole body in the `field_mappings` JSONB column. The normalizer reads `field_mappings['mapping']` at runtime. I traced the endpoint in `backend/modules/suppliers/routes.py` line 92 and confirmed the payload shape."*

### Q: "Is this ready for production?"

**A:** *"The unit tests prove the logic is correct. Ready for Urvashi's Task 16 (sync route) to wire it up. The E2E confirmation against real 4Over data happens once Christian provides sandbox credentials — not a code risk, just a pending validation step."*

---

## 7. Evidence You Can Screenshot

### Screenshot 1 — All tests passing

Run:
```bash
cd "$(git rev-parse --show-toplevel)/backend" && source .venv/bin/activate
python test_fourover_normalizer.py && python test_fourover_client.py
```

Caption: *"7 new normalizer tests + 9 regression tests for the Task 14 client — 16 tests total, all pass."*

### Screenshot 2 — Live normalization of a 4Over product

Run the Command 3 snippet above. Caption:
*"Live demo. Notice that `coating: 'UV'` was not in the mapping config, but the normalizer still captured it in the variant's `attributes` dict so no data is lost."*

### Screenshot 3 — The attributes dict in action

Paste this into a Python REPL started in the `backend` folder:

```python
from modules.promostandards.schemas import PSProductPart

# Old SanMar-style part — no attributes
apparel = PSProductPart(part_id="PC61-NAVY-M", color_name="Navy", size_name="M")
print("SanMar (apparel):", apparel.attributes)

# New 4Over-style part — with attributes
print_product = PSProductPart(
    part_id="brochure-001",
    color_name="Glossy",
    size_name="Tri",
    attributes={"coating": "UV", "paper_weight": "100gsm"}
)
print("4Over (print):   ", print_product.attributes)
```

Expected:
```
SanMar (apparel): {}
4Over (print):    {'coating': 'UV', 'paper_weight': '100gsm'}
```

Caption: *"The `attributes` field defaults to `{}` for SanMar's apparel-style variants (zero impact) and carries 4Over's extra axes when needed. Backward-compatible extension."*

---

## 8. What's NOT Yet Tested

**E2E against real 4Over sandbox** — blocked on Christian's credentials. When available:

1. Save a field mapping for 4Over in the UI at `/mappings/{4over_id}`.
2. Run the sync via Urvashi's Task 16 endpoint (once that ships).
3. Verify products appear in `GET /api/products?supplier_id={4over_id}`.

**What to say about the blocker:**
> "The unit tests prove the translation logic is correct. The E2E would only confirm the exact shape of 4Over's real response matches our default expectations — if it doesn't, the fix is a one-line keyword argument change."

---

## 9. One-Line Standup Summary

> "Task 15 shipped — 4Over normalizer, 7/7 tests green, 9 Task 14 regression tests still pass. Sprint complete 6/6. Commit `44033bb` on `Vidhi`."

---

## 10. Before Running Tests (Setup Checklist)

```bash
# 1. Pull latest
cd "$(git rev-parse --show-toplevel)"
git fetch origin
git checkout Vidhi
git pull origin Vidhi

# 2. Activate venv
cd backend
source .venv/bin/activate

# 3. Run all the 4Over tests
python test_fourover_normalizer.py
python test_fourover_client.py
```

No Postgres needed. No network. Under 2 seconds total runtime.
