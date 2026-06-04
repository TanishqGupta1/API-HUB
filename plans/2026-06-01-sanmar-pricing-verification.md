# SanMar Pricing & Markup Verification — Implementation Plan

**Date:** 2026-06-01
**Author:** Vidhi
**Status:** ACTIVE — VG print push plan deferred per team lead
**Goal:** Verify SanMar pricing end-to-end before any live OPS push goes out

---

## 1. Why this comes before anything else

Team lead direction: focus on SanMar first. We are setting markup rules and pricing locally — before we push to OPS, we have to prove the prices we will quote customers are correct in three ways:

- **Q1**: Are the wholesale base prices we synced from SanMar actually right?
- **Q2**: Does our markup rule produce a sensible retail price?
- **Q3**: Do **all 886 variants** price correctly (not just the ones we sampled)?

This is a business-correctness gate, not a code gate. If pricing is wrong, every push downstream is wrong.

---

## 2. The pricing pipeline (what we're verifying)

```
SanMar wholesale price (from SOAP getConfigurationAndPricing)
        ↓
stored in product_variants.base_price (DB column)
        ↓
markup_rules engine (resolve_rule + apply_markup)
        ↓
final retail price → goes to OPS as setProductPrice.price
                  → setProductPrice.vendor_price = base_price
```

We have **three trustworthy endpoints** for verification — all already exist:

| Endpoint | What it returns | Auth | Use for |
|---|---|---|---|
| `GET /api/pricing/quote` | base cost only (no customer markup) | public | sanity-check synced base prices |
| `POST /api/customers/{id}/pricing/quote` | base + final + margin per variant for a specific customer | internal | end-to-end markup verification |
| `GET /api/push/{customer_id}/product/{product_id}/payload` | the exact mutation plan that would be pushed to OPS (with final_price embedded) | ingest secret | ground truth — confirms quote and push agree |

---

## 3. Current state (snapshot)

- **68 SanMar products** synced into DB
- **886 variants total** across those products
- **All variants have valid `base_price`** (no nulls, no zeros) — already verified by team lead
- **Markup engine** exists at `backend/modules/markup/engine.py` (`resolve_rule` + `apply_markup`)
- **Scope hierarchy** supported: Supplier → Category → Product (higher priority wins)
- **Pricing endpoints** all exist (`backend/modules/pricing/routes.py`)

What is NOT verified yet:
- Whether `base_price` values match SanMar's published wholesale price sheet
- Whether the markup % gives Visual Graphics the margin they actually want
- Whether all 886 variants resolve cleanly to a final price (no missed rules, no zero output)
- Whether the push payload `final_price` is identical to the `/pricing/quote` final_price

---

## 4. Three-step verification workflow

### Step 1 — Spot-check base prices against SanMar's published list

Pick 6 SKUs across categories (so we cover the price range and product types):

| SanMar SKU | Product | Expected wholesale (from sanmar.com price sheet) | Our DB base_price | Pass? |
|---|---|---|---|---|
| PC54 | Core Cotton Tee | ~$3.49 | _to fill_ | _to fill_ |
| PC450 | Fan Favorite Tee | ~$5.99 | _to fill_ | _to fill_ |
| L500 | Women's Polo | ~$12–16 | _to fill_ | _to fill_ |
| OGIO duffel (one SKU) | Duffel bag | ~$46.95 | _to fill_ | _to fill_ |
| CP90 | Knit cap | _to fill_ | _to fill_ | _to fill_ |
| One outerwear SKU | Jacket | _to fill_ | _to fill_ | _to fill_ |

**How**:
```bash
docker compose exec postgres psql -U vg_user -d vg_hub -c \
  "SELECT p.supplier_sku, v.color, v.size, v.base_price
     FROM products p JOIN product_variants v ON v.product_id = p.id
    WHERE p.supplier_sku IN ('PC54','PC450','L500','CP90')
    ORDER BY p.supplier_sku, v.color, v.size;"
```

Then open sanmar.com → product page → wholesale price → compare. Save the comparison in `docs/sanmar_pricing_audit.md`.

**Pass criterion**: every spot-check matches SanMar's published wholesale within ±$0.05.

---

### Step 2 — Decide markup target with team lead

We need this answer **before** configuring rules:

- **One global markup** across all SanMar (simple, e.g. 45%)?
- **Per-category** (bags 30%, tees 45%, polos 40%)?
- **Per-product overrides** for high-volume SKUs?

The team lead message showed an example: 45% markup on PC54 ($3.49 → $5.99) = ~42% margin. That works for tees but might be wrong for bags ($46.95 → $68.08 = 31% margin which may be too thin).

Document the decision in `docs/sanmar_pricing_audit.md` so it's reviewable.

---

### Step 3 — Configure scoped markup rules

Once targets are decided, configure rules in the admin `/markup` page using the scope hierarchy the engine already supports:

```
Scope            Priority  Markup    Purpose
─────────────────────────────────────────────────────────────────
Supplier=sanmar    1       45%       Default for all SanMar products
Category=Bags      2       30%       Lower margin, more competitive
Category=Caps      2       40%       Mid-tier accessories
Product=PC54       3       42%       Specific high-volume override
```

The engine picks the most specific (highest priority) rule that matches.

---

### Step 4 — Run the 886-variant sweep

Loop every SanMar variant through `POST /api/customers/{id}/pricing/quote`. Build a CSV report:

```
product_sku, variant_sku, color, size, base_price, final_price, margin_pct, rule_id, rule_scope
PC54,        PC54-WHT-S,  White, S,    3.49,        5.99,        41.7,        abc-123,  category=Tees
PC54,        PC54-BLK-M,  Black, M,    3.49,        5.99,        41.7,        abc-123,  category=Tees
...
```

**Auto-flag any row where**:
- `final_price <= base_price` → markup rule broken
- `rule_id` is null → no rule matched (config gap)
- `margin_pct` is outside expected range for that category
- `final_price` is null → engine failure

**Pass criterion**: zero unexplained flags across all 886 variants.

---

### Step 5 — Cross-check quote vs push payload

For 5–10 sample products, call both endpoints and assert equality:

```bash
# Quote
curl -X POST http://localhost:8000/api/customers/$CUST/pricing/quote \
  -H 'Content-Type: application/json' \
  -d '{"product_id":"'$PROD'","variants":[]}'

# Push payload
curl -H "X-Ingest-Secret: $INGEST_SECRET" \
  http://localhost:8000/api/push/$CUST/product/$PROD/payload
```

For every variant, `quote.final_price == payload.setProductPrice.price`. If they diverge, the markup engine is running differently in the two code paths — that's a critical bug we must fix before any push.

---

## 5. Concrete tasks (7 tasks tracked in TaskList)

| # | Task | Owner | Effort | Blocks |
|---|---|---|---|---|
| 11 | Q1 — Verify base prices against SanMar's published list (6 SKU spot check) | Vidhi | 1h | 13 |
| 12 | Q2 — Decide markup target with team lead | team lead | meeting | 13 |
| 13 | Configure scoped markup rules in admin UI | Vidhi | 30m | 14 |
| 14 | Q3 — Verify all 886 variant prices via `/pricing/quote`, generate CSV | Vidhi | 2h | 15 |
| 15 | Cross-check push payload `final_price` matches quote | Vidhi | 1h | — |
| 16 | Build pricing audit script/UI for reuse (`backend/scripts/audit_pricing.py` or `/markup/audit` page) | Vidhi | 3h | — |
| 17 | Write `docs/sanmar_pricing_runbook.md` so ops can repeat the verification | Vidhi | 1h | — |

**Total: ~8.5h dev + 1 team meeting.**

---

## 6. What this plan does NOT do

- Does not push anything to OPS — that's the next phase, gated on completing this verification
- Does not change the markup engine — only configures rules
- Does not change pricing data — only audits it
- Does not touch VG print products (plan `plans/2026-06-01-vg-print-product-push.md` is deferred until this lands)

---

## 7. Definition of done

- [ ] 6 spot-checked SanMar SKUs match published wholesale within ±$0.05
- [ ] Markup target decision documented and signed off by team lead
- [ ] Markup rules configured per the decision
- [ ] All 886 variants resolve to a non-zero `final_price` with a matching `rule_id`
- [ ] Quote endpoint and push payload endpoint agree on `final_price` for 5–10 sample products
- [ ] Reusable audit script or admin page exists (`/markup/audit` or `backend/scripts/audit_pricing.py`)
- [ ] Runbook published in `docs/sanmar_pricing_runbook.md`
- [ ] Team lead reviews CSV output and approves moving to live push

---

## 8. The one risk

**Risk**: SanMar may publish tiered prices (quantity breaks). Today we store one `base_price` per variant — the "piece" tier at qty=1. If Visual Graphics wants to sell at qty-break pricing, we are short a feature.

**Mitigation**: this plan ships single-tier pricing first (matches what we sync). Multi-tier pricing is a follow-up plan only if the business needs it.
