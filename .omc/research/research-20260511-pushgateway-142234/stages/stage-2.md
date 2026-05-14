# Stage 2 — Bug Analysis: SanMar → OPS Push Blockers

**Source files analysed (read-only):**
- `backend/scripts/sanmar_ops_spike.py` (293 lines)
- `docs/superpowers/specs/2026-05-08-sanmar-ops-staging-push-design.md`
- `backend/modules/promostandards/ps_normalizer_v2.py`
- `backend/modules/promostandards/adapter.py`
- `backend/modules/promostandards/sanmar_adapter.py`
- `backend/modules/promostandards/client.py`
- `backend/modules/promostandards/normalizer.py` (legacy)
- `backend/modules/markup/engine.py`
- `backend/modules/ops_push/service.py`

---

## [FINDING:F2.0] Spike Script — What 4 Checks Does It Run?

`sanmar_ops_spike.py` runs **9 numbered sections** but the 4 substantive bug-confirming
checks (sections 3, 4, 6, 7) map to the 4 spec bugs as follows:

| Section | Label | What it verifies | Bug confirmed? |
|---------|-------|------------------|----------------|
| 1 | Load SanMar supplier row | DB row exists + has auth_config.id/password | Prereq only |
| 2 | Hydrate PC61 via SanMarAdapter | Full ProductIngest returned without error | Prereq only |
| 3 | base_price bug check (first 3 variants) | Checks `v.base_price is None` on each variant; also runs `_pick_min_net()` to show what the fix WOULD set | **Bug 1 confirmed** — appends `"base_price_none_bug"` to failures |
| 4 | Inventory bug check | `any(v.inventory is not None …)` — if all None, inventory SOAP was never called | **Bug 2 confirmed** — appends `"inventory_soap_not_called"` |
| 5 | Image presence | Warns if `ingest.images` empty | Informational / warning only |
| 6 | Load VG OPS customer row | Checks all four OAuth2 fields present (ops_base_url, ops_token_url, ops_client_id, client_secret) | Bug 4 prereq gate |
| 7 | OAuth2 client_credentials probe | POST to ops_token_url; checks HTTP 200 + access_token present | **Bug 4 PASSES** per spec |
| 8 | Sample setProduct mutation (NOT sent) | Preview of what payload_builder would emit | Informational |
| 9 | Sample setProductPrice for variants[0] | Shows backfill + 50% markup calculation inline | Bug 3 implication visible here |

**Bug 3 (markup bypass) is NOT directly asserted** by the spike script — section 9 shows
the correct markup computation inline as a demo, but the script never calls
`ops_push/service.py` or `markup/engine.py`. The spec and service.py code confirm Bug 3
independently (see F2.3 below).

**Execution order matters:** sections 1 and 2 are fail-fast (return 2 or 1 immediately
on failure). Sections 3 and 4 are cumulative — both append to `failures[]` and the
script continues. Section 6 has an early `return 1` if fields are missing.

---

## [FINDING:F2.1] Bug 1 — base_price=None on Modern Normalizer Path

**Root cause — file:line:**
`backend/modules/promostandards/ps_normalizer_v2.py`, function `merge_pricing`, lines 142–166.

Specifically line 161–165:
```python
by_part[pid].prices.append(VariantPriceIngest(
    price_type=discount_code,
    quantity_min=int(qmin) if qmin else 1,
    price=Decimal(value),
))
```

`merge_pricing` **only appends price tiers to `variant.prices[]`**. It never sets
`variant.base_price`. The `VariantIngest` object is constructed in
`normalize_get_product_xml` (line 93–100) with `prices=[]` and **no `base_price`
argument** — Pydantic defaults it to `None`.

The legacy path (`normalizer.py::_pick_base_price`, line 44–50) correctly picks
the minimum "piece" tier and assigns it to the DB column. The modern V2 path has
no equivalent assignment.

**Symptom:**
After `hydrate_product` returns, every `VariantIngest.base_price` is `None`,
even though `variant.prices` is populated with Net-tier `VariantPriceIngest` rows.
The spike confirms this by checking `v.base_price is None` on the first 3 variants
and showing `_pick_min_net(v.prices)` returns a real value.

**Minimal fix (≤15 LOC) — add to `merge_pricing` after the loop:**
```python
def merge_pricing(ingest: ProductIngest, pricing_xml: bytes) -> ProductIngest:
    # ... existing loop that populates variant.prices ...
    root = etree.fromstring(pricing_xml, _PARSER)
    parts = root.xpath("//*[local-name()='PartPricing'] | //*[local-name()='Part']")
    by_part = {v.part_id: v for v in ingest.variants}

    for part in parts:
        pid = _text(part, "*[local-name()='partId']")
        if not pid or pid not in by_part:
            continue
        price_nodes = part.xpath("...")
        for pp in price_nodes:
            # ... existing append logic ...
            pass

    # NEW: backfill base_price from min Net-tier qty_min=1 price
    for variant in ingest.variants:
        if variant.base_price is None and variant.prices:
            nets = [
                p for p in variant.prices
                if p.price_type and p.price_type.lower() in ("net", "net price")
            ]
            if nets:
                variant.base_price = min(
                    nets, key=lambda p: (p.quantity_min, p.price)
                ).price
    return ingest
```

This mirrors `_pick_min_net` already present in the spike script itself (lines 60–68),
confirming the spec authors already documented the exact fix logic.

**Confidence: HIGH** — root cause is unambiguous from direct code read. No Net-tier
assignment exists anywhere in the V2 path. Spike helper `_pick_min_net` is the
exact fix expressed as documentation.

---

## [FINDING:F2.2] Bug 2 — Inventory v200 SOAP Not Called

**Root cause — file:line:**
`backend/modules/promostandards/adapter.py`, function `hydrate_product`, lines 129–153.

The method calls three services in sequence:
1. `_call_get_product(ref)` → product XML
2. `_call_get_pricing(ref)` → pricing XML  
3. `_call_get_media(ref)` → media XML

There is **no call to `_call_get_inventory(ref)`** (nor does such a method exist on
`PromoStandardsAdapter` yet). The `INVENTORY` key is present in `SanMarAdapter.SANMAR_WSDLS`
(sanmar_adapter.py line 21: `"INVENTORY": "https://promostandards.sanmar.com/InventoryService/v200?wsdl"`)
confirming the WSDL is known and wired — but `hydrate_product` never calls it.

`PromoStandardsClient` has `get_inventory()` and `_sync_get_inventory()` implemented in
`client.py` lines 606–626, using `getInventoryLevels` SOAP operation. The parse logic
is also complete (lines 629–657). The capability exists; it is simply not invoked.

**Symptom:**
`variant.inventory` is `None` for all variants after hydration. The spike checks
`any(v.inventory is not None for v in ingest.variants)` — if all None,
appends `"inventory_soap_not_called"` to failures.

**Minimal fix — add `_call_get_inventory` to `adapter.py` and call it from `hydrate_product`:**
```python
# In adapter.py: add method alongside _call_get_media
async def _call_get_inventory(self, ref: ProductRef) -> list:
    client = self._get_client("INVENTORY")
    return await client.get_inventory([ref.supplier_sku])

# In hydrate_product, after merge_media block:
try:
    inventory_levels = await self._call_get_inventory(ref)
    # build lookup by part_id
    inv_by_part = {level.part_id: level for level in inventory_levels}
    for variant in ingest.variants:
        level = inv_by_part.get(variant.part_id)
        if level:
            variant.inventory = level.quantity_available
except Exception as exc:
    log.warning("Inventory fetch failed for %s: %s", ref.supplier_sku, exc)
```

Also need a corresponding `merge_inventory` helper in `ps_normalizer_v2.py` for
symmetry with `merge_pricing`/`merge_media`, but the inline approach above in
`adapter.py` is sufficient for the minimal fix.

**Confidence: HIGH** — the INVENTORY WSDL key is defined, client parse logic is fully
implemented, `hydrate_product` simply has no call site. No ambiguity.

---

## [FINDING:F2.3] Bug 3 — Markup Engine Bypassed by Push

**Root cause — file:line:**
`backend/modules/ops_push/service.py`, function `push_product`, lines 76–83.

```python
# line 76
payload = merge_product_with_decorations(product, dec_options)
```

`merge_product_with_decorations` (imported from `.merge`) assembles the push payload
from the raw `product` ORM object. `product.variants` have `base_price` (the raw
supplier net price). At **no point** in `push_product` is `markup/engine.py` consulted.

Specifically:
- `markup.engine.resolve_rule` is never imported or called in `service.py`
- `markup.engine.apply_markup` is never called
- `markup.engine.calculate_price` (the full DB-loading helper) is never called
- The `payload` dict sent to n8n contains raw `base_price` values from DB

The markup engine is only used in `markup/routes.py` (the `/payload` endpoint), which
is a separate read-only inspection endpoint — it does NOT feed into the push path.
The spec acknowledges this under "Deprecated routes": `GET /customers/{cid}/products/{pid}/payload`
has live callers but the push service never calls into it.

**Symptom:**
Products arrive at OPS staging with vendor net price as the displayed price.
A product with `base_price = $8.32` would be pushed as `price = $8.32` rather than
`$12.48` (50% markup). No `markup_rule` or `vendor_price` separation exists in the
n8n payload.

**Minimal fix — inject markup resolution into `push_product` before payload assembly:**
```python
# In service.py, after loading `product` and `customer`:
from modules.markup.engine import apply_markup, resolve_rule
from modules.markup.models import MarkupRule
from sqlalchemy import select as sa_select

rules = (
    await db.execute(
        sa_select(MarkupRule).where(MarkupRule.customer_id == customer_id)
    )
).scalars().all()
rule = resolve_rule(rules, product.supplier_sku, product.category)

# Then pass rule into merge_product_with_decorations, or apply post-merge:
payload = merge_product_with_decorations(product, dec_options)
for variant in payload.get("variants", []):
    base = variant.get("base_price")
    if base is not None:
        from decimal import Decimal
        variant["vendor_price"] = base
        variant["final_price"] = float(apply_markup(Decimal(str(base)), rule) or base)
```

Note: the spec intends this to be fully absorbed into the new `payload_builder.py`
module rather than patching the legacy service. The minimal fix above unblocks the
current push path. The clean fix is `payload_builder.py` as described in the spec.

**Confidence: HIGH** — `service.py` contains zero imports from `modules.markup`. The
code path from `push_product` to n8n payload is completely markup-free. Verified by
direct read of all 156 lines of `service.py`.

---

## [FINDING:F2.4] Bug 4 — VG Customer OAuth2 Flow (PASSES — Confirm Scope)

**What the spike verifies (sections 6 and 7):**

Section 6 (lines 163–190) checks that the `Customer` DB row has all four required fields:
- `ops_base_url` — non-empty
- `ops_token_url` — non-empty  
- `ops_client_id` — non-empty
- `ops_auth_config.client_secret` — non-empty (decrypted from EncryptedJSON)

If any field is missing → appends `"customer_creds_incomplete"` and `return 1` immediately.

Section 7 (lines 192–214) performs a **live HTTP POST** to `customer.ops_token_url` with
`grant_type=client_credentials` + `client_id` + `client_secret`. Checks:
- HTTP 200 response
- `response.json().get("access_token")` is non-empty

Per spec: "VG OPS staging customer row already seeded." Per spec acceptance criteria #7:
"VG customer OAuth2 flow — this one PASSES per spec."

**Evidence:**
The spike explicitly prints `access_token length=<N>` on success. The `failures[]` list
never gets `"oauth2_failed"` or `"oauth2_threw"` appended when the check passes. The
summary section (line 262–272) would print "all credential + reachability checks passed"
if only the OAuth2 checks run (i.e., if base_price and inventory bugs were fixed).

**Scope of what PASSES:** token issuance only — the OAuth2 credential round-trip to
`ops_token_url`. The spike does NOT verify:
- That the token scope grants `setProduct`/`setProductPrice` mutations
- That `ops_base_url/graphql` accepts the token (no GraphQL call is made)
- Token expiry / refresh behaviour mid-push

**Confidence: HIGH** — the spike is explicit that sections 8 and 9 are "NOT sent —
preview only". No OPS write path is exercised. OAuth2 credential validity is confirmed;
GraphQL authorization scope is not.

---

## [FINDING:F2.5] Cross-Cutting — Shared Root Causes and Fix Order

**Are any 2 bugs the same root cause?**

No — all four bugs are distinct root causes in distinct files:

| Bug | Root file | Root cause class |
|-----|-----------|-----------------|
| 1 (base_price=None) | `ps_normalizer_v2.py::merge_pricing` | Missing scalar assignment after price-tier loop |
| 2 (inventory not called) | `adapter.py::hydrate_product` | Missing call site (method exists, not invoked) |
| 3 (markup bypassed) | `ops_push/service.py::push_product` | Missing engine import and call |
| 4 (OAuth2) | Customer DB row | PASSES — no code bug |

**However, Bugs 1 and 2 share a structural pattern:** the modern V2 adapter path
(`ps_normalizer_v2.py` + `adapter.py`) is incomplete relative to the legacy path
(`normalizer.py`). The legacy normalizer handled base_price assignment AND received
inventory as a parameter. The V2 rewrite omitted both. This is one architectural
gap expressed as two separate missing features.

**Fix order matters — recommended sequence:**

1. **Fix Bug 1 first** (base_price backfill in `merge_pricing`). This is a prerequisite
   for the preflight check `base_price_set` to pass, which blocks the push pipeline
   from even starting. Preflight validator in spec check #1 explicitly gates on this.

2. **Fix Bug 2 second** (inventory SOAP call). This is independent of Bug 1 but
   inventory=None causes missing stock data in OPS. Not a hard blocker for preflight
   (spec preflight has no `inventory_present` check) but produces incorrect product data.

3. **Fix Bug 3 third** (markup engine in push path). Requires Bug 1 fixed first —
   `apply_markup(None, rule)` returns `None` (see `engine.py` line 53:
   `if base_price is None: return None`). If Bug 1 is not fixed, markup produces
   no output anyway. Fix Bug 1 → then Bug 3 produces correct final prices.

4. **Bug 4 is already passing** — no action needed for credentials.

**Summary fix chain:** `merge_pricing` backfill → `hydrate_product` inventory call →
`push_product` markup injection → pipeline is unblocked end-to-end.

[STAT:n] 4 bugs identified across 4 distinct files
[STAT:effect_size] All 4 are blocking or data-corrupting; 0 are cosmetic
[LIMITATION] Bug 3 minimal fix patches `service.py` (legacy push path). Spec intends
full replacement via `payload_builder.py`. The minimal fix is a bridge only.
[LIMITATION] Bug 2 inventory fix assumes SanMar Inventory v200 SOAP response shape
matches `client.py::_parse_inventory` expectations — not verified against live data in this analysis.
[LIMITATION] Bug 4 OAuth2 scope confirmation (GraphQL mutation authorization) requires
a live dry-run test against OPS staging — not verifiable from code alone.
