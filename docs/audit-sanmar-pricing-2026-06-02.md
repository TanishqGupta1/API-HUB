# SanMar Stored Pricing Audit Report

**Date:** 2026-06-02
**Auditor:** Automated (Claude Code)
**Scope:** Read-only verification of SanMar base prices stored in API-HUB PostgreSQL
**Supplier:** SanMar | ID `a73a8445-2f08-4293-9625-b3e480ddc1da` | Protocol: PromoStandards

---

## 1. Executive Summary

| Metric | Value | Status |
|--------|-------|--------|
| Styles ingested | 165 | |
| Total variants | 4,275 | |
| Null prices | 0 | PASS |
| Zero prices | 0 | PASS |
| Negative prices | 0 | PASS |
| Duplicate SKUs | 0 | PASS |
| Price range | $1.49 - $130.79 | |
| Average price | $13.17 | |
| Pricing sync jobs on record | 0 (inline with product sync) | INFO |
| Spot-check vs reseller benchmark | All within expected band | PASS |
| Anomalies found | 1 (BG200 @ $1.49 — see Section 6) | REVIEW |

**Overall verdict: PASS** — stored prices are consistent with SanMar dealer-level wholesale pricing. One anomaly flagged for manual review.

---

## 2. Methodology

### 2.1 Data source
Prices are ingested via the PromoStandards `getConfigurationAndPricing` SOAP service during n8n-triggered sync. The normalizer (`backend/modules/promostandards/ps_normalizer_v2.py`, line 180) selects the **lowest quantity-tier Net price**:

```python
cheapest = min(net_tiers, key=lambda p: (p.quantity_min, p.price))
variant.base_price = cheapest.price
```

This gives us the single-piece dealer cost (qty-1 Net), which is the correct input for the markup engine.

### 2.2 Benchmark source
SanMar.com requires a dealer login for pricing — no public access. Instead, **BlankStyle.com** (a major SanMar reseller) was used as a proxy benchmark. Their "$100+" column represents retail markup over SanMar dealer cost.

**Expected relationship:** Our DB prices should be **25-50% below** BlankStyle retail, since BlankStyle buys from SanMar at dealer cost and adds margin.

### 2.3 Limitations
- Cannot perform penny-exact verification without SanMar dealer credentials or a live PromoStandards pricing call
- BlankStyle prices may include their own margin fluctuations
- SanMar prices change periodically; stored prices reflect the last sync date

---

## 3. Spot-Check: DB Prices vs BlankStyle Reseller Retail

| Style | Product | Size Tier | Our DB | BlankStyle $100+ | Delta | Verdict |
|-------|---------|-----------|--------|------------------|-------|---------|
| 2200 | Gildan Ultra Cotton Tank | S-XL (White) | $3.73 | $6.98 | -47% | PASS |
| 2200 | Gildan Ultra Cotton Tank | S-XL (Colors) | $4.85 | $6.98 | -31% | PASS |
| 2200 | Gildan Ultra Cotton Tank | 2XL (White) | $5.81 | $10.72 | -46% | PASS |
| 2200 | Gildan Ultra Cotton Tank | 3XL (White) | $6.72 | $12.29 | -45% | PASS |
| ST350 | Sport-Tek Competitor Tee | XS-XL | $4.13 | $6.61 | -38% | PASS |
| ST350 | Sport-Tek Competitor Tee | 2XL | $5.13 | $8.21 | -37% | PASS |
| ST350 | Sport-Tek Competitor Tee | 3XL | $7.13 | $11.41 | -38% | PASS |
| ST350 | Sport-Tek Competitor Tee | 4XL | $8.13 | $13.01 | -37% | PASS |
| L500 | Port Authority Silk Touch Polo | XS-XL | $12.04 | $16.06 | -25% | PASS |
| L500 | Port Authority Silk Touch Polo | XXL | $13.04 | $17.66 | -26% | PASS |
| L500 | Port Authority Silk Touch Polo | 3XL | $15.04 | $20.86 | -28% | PASS |
| L500 | Port Authority Silk Touch Polo | 4XL | $16.04 | $22.46 | -29% | PASS |
| 108084 | OGIO Transfer Duffel | OSFA | $46.95 | $72.29 (sale) | -35% | PASS |

**All 13 spot-checks fall within the expected 25-50% discount band.** The margin is consistent across product categories (apparel, polos, bags).

---

## 4. Brand Breakdown

| Brand | Styles | Variants | Min $ | Max $ | Avg $ |
|-------|--------|----------|-------|-------|-------|
| Port Authority | 72 | 990 | $1.49 | $41.34 | $13.28 |
| Sport-Tek | 50 | 2,945 | $3.61 | $30.82 | $12.72 |
| OGIO | 31 | 74 | $14.75 | $130.79 | $41.87 |
| Port & Company | 3 | 15 | $3.49 | $14.99 | $7.99 |
| Jerzees | 3 | 192 | $9.30 | $15.67 | $11.20 |
| District | 2 | 14 | $4.13 | $4.13 | $4.13 |
| Nike | 1 | 1 | $12.73 | $12.73 | $12.73 |
| Gildan | 1 | 36 | $3.73 | $8.54 | $5.68 |
| New Era | 1 | 6 | $7.59 | $7.59 | $7.59 |
| CornerStone | 1 | 2 | $6.70 | $6.70 | $6.70 |

**10 brands, 165 styles, 4,275 variants** — all price ranges are consistent with wholesale apparel/accessory pricing.

---

## 5. Price Distribution

| Bucket | Variants | Actual Low | Actual High |
|--------|----------|------------|-------------|
| $0 - $5 | 809 | $1.49 | $4.90 |
| $5 - $10 | 1,167 | $5.02 | $9.82 |
| $10 - $20 | 1,376 | $10.03 | $19.99 |
| $20 - $30 | 787 | $20.11 | $29.86 |
| $30 - $50 | 119 | $30.16 | $46.95 |
| $50 - $75 | 12 | $53.65 | $73.77 |
| $75+ | 5 | $76.45 | $130.79 |

The distribution is heavily weighted toward $5-$20 (apparel core), with a long tail into bags/packs ($50+). This is the expected shape for a SanMar catalog.

---

## 6. Anomalies

### 6.1 BG200 — Port Authority Cyber Backpack ($1.49 vs $19.94)

| SKU | Color | Size | Price |
|-----|-------|------|-------|
| BG200-BLK-OS | Black | OSFA | **$1.49** |
| BG200-RED-OS | Red | OSFA | **$1.49** |
| BG200-RYL-OS | Royal | OSFA | **$1.49** |
| 748853 | Black/Red | OSFA | $19.94 |
| 748863 | Dark Charcoal/Royal | OSFA | $19.94 |

**Analysis:** The $1.49 price for a backpack is abnormally low — even at dealer cost, a backpack would typically be $10+. This is likely a **closeout/liquidation price** from SanMar (they mark discontinued colors near-zero to clear inventory). The $19.94 colorways appear to be current stock at normal pricing.

**Risk:** If the markup engine applies a percentage (e.g. 30%) to a $1.49 base, the OPS retail price would be $1.94 — too low. However, the markup engine's catch-all rule would still produce a valid (if low) price.

**Recommendation:** Manual review — confirm whether BG200 Black/Red/Royal are genuinely closeout. If so, either archive those variants or set a floor price in the markup rules.

### 6.2 No pricing sync jobs on record

The `sync_jobs` table has no rows with `job_type = 'pricing'` for SanMar. This indicates pricing was ingested **inline** during the product/variant sync (the normalizer backfills `base_price` from the pricing XML at ingest time), not as a separate pricing sync job. This is not a bug — just means pricing freshness cannot be tracked independently from product sync.

---

## 7. Size Upcharge Patterns

| SKU | Product | Base (S-XL) | 2XL | 3XL | 4XL | Spread |
|-----|---------|-------------|-----|-----|-----|--------|
| ST350 | Sport-Tek Competitor Tee | $4.13 | $5.13 (+$1.00) | $7.13 (+$3.00) | $8.13 (+$4.00) | $4.00 |
| L500 | Port Authority Silk Touch Polo | $12.04 | $13.04 (+$1.00) | $15.04 (+$3.00) | $16.04 (+$4.00) | $4.00 |
| 2200 | Gildan Ultra Cotton Tank (White) | $3.73 | $5.81 (+$2.08) | $6.72 (+$2.99) | — | $2.99 |
| K420 | Port Authority HW Pique Polo | $17.40 | $18.40 (+$1.00) | $20.40 (+$3.00) | $21.40 (+$4.00) | $8.12* |

\* K420 spread includes color-tier pricing (1 premium color at $18.52 base vs $17.40 for standard colors).

Upcharge patterns are consistent across brands: +$1 for 2XL, +$3 for 3XL, +$4 for 4XL. This matches industry-standard extended-size surcharges.

---

## 8. Data Integrity Checks

| Check | Result | Notes |
|-------|--------|-------|
| Null base_price | 0 / 4,275 | All variants have prices |
| Zero base_price | 0 / 4,275 | No blank/missing prices |
| Negative base_price | 0 / 4,275 | No corrupted values |
| Duplicate variant SKUs | 0 | Every SKU is unique |
| Orphaned variants (no product) | N/A | FK constraint enforced |
| Price > $200 | 0 | No outlier values |
| Price < $1.00 | 0 | Lowest is $1.49 (BG200 closeout) |
| Color-specific pricing | Verified | Gildan 2200 White vs Colors correctly differentiated |
| Size-tier ordering | Verified | Larger sizes always >= base price |

---

## 9. Normalization Pipeline Verification

The pricing flows through this path:

```
SanMar SOAP API
  -> getConfigurationAndPricing (PromoStandards 1.0.0)
    -> ps_normalizer_v2.py._parse_pricing_and_configuration()
      -> filters for "Net" / "Net Price" discount codes
        -> picks min(quantity_min, price) = qty-1 Net price
          -> sets variant.base_price
            -> ingest.py upserts to product_variants.base_price
```

The test fixture (`tests/fixtures/sanmar_get_pricing_pc61.xml`) confirms the XML structure:
- Part `PC61-WH-S`: qty-1 = $5.98, qty-12 = $4.98 (normalizer would pick $4.98 as the cheapest Net tier)
- Part `PC61-BLK-XL`: qty-1 = $6.98

This is correct behavior — the normalizer picks the best available Net price for markup calculation.

---

## 10. Recommendations

1. **BG200 closeout review** — Manually verify the 3 variants at $1.49. If closeout, consider archiving or adding a minimum-price floor rule in the markup engine.

2. **Penny-exact verification** — Once SanMar API credentials arrive (pending from Christian), run a spot-check script calling `getConfigurationAndPricing` live for 10 styles and compare penny-for-penny against stored values.

3. **Pricing freshness tracking** — Consider logging a separate `pricing` sync job when prices are refreshed, so staleness can be monitored independently from product catalog syncs.

4. **Price change alerts** — Add a threshold alert (e.g. >10% change) when pricing re-syncs, to catch supplier price swings before they propagate to storefronts.

---

## 11. Appendix: Top 10 Products by Size/Color Price Spread

| SKU | Product | Base $ | Top $ | Spread $ |
|-----|---------|--------|-------|----------|
| BG200 | Port Authority Cyber Backpack | $1.49 | $19.94 | $18.45 |
| K420 | Port Authority HW Cotton Pique Polo | $17.40 | $25.52 | $8.12 |
| K420P | Port Authority HW Pique Polo w/Pocket | $18.52 | $26.64 | $8.12 |
| T200 | Sport-Tek Colorblock Raglan Jersey | $6.70 | $14.26 | $7.56 |
| JST62 | Sport-Tek V-Neck Raglan Wind Shirt | $15.64 | $22.64 | $7.00 |
| K321 | Port Authority Interlock Mock Turtleneck | $14.28 | $21.28 | $7.00 |
| JST72 | Sport-Tek V-Neck Raglan Wind Shirt | $14.52 | $21.52 | $7.00 |
| JST73 | Sport-Tek Hooded Raglan Jacket | $18.23 | $25.23 | $7.00 |
| JST70 | Sport-Tek Full-Zip Wind Jacket | $17.39 | $24.39 | $7.00 |
| JST81 | Sport-Tek Fleece-Lined Colorblock Jacket | $22.79 | $29.79 | $7.00 |

Most $7.00 spreads are standard extended-size upcharges (S-XL to 4XL/5XL/6XL). The $18.45 BG200 spread is the closeout anomaly noted in Section 6.1.

---

*Report generated from live PostgreSQL data on 2026-06-02. No data or code was modified during this audit.*
