# Tanishq — Sprint Tasks

**Total: 3 tasks** (core pipeline — complex, can't delegate) + PR reviews

---

## Task 3b: SOAP Client (client.py)

**Priority:** After Vidhi's Task 3 (resolver.py) and Sinchana's Task 2 (schemas) are merged.
**File to create:** `backend/modules/promostandards/client.py`
**Depends on:** `resolver.py` (Task 3 by Vidhi), `schemas.py` (Task 2 by Sinchana)

### What this does
The core protocol adapter. Uses zeep to make SOAP calls to any PromoStandards supplier. Takes a WSDL URL + credentials from the database. Returns typed Pydantic models (PSProductData, PSInventoryLevel) that the normalizer consumes.

### Key technical decisions
- zeep is **synchronous** — all calls wrapped with `asyncio.to_thread()` to avoid blocking FastAPI
- `zeep.cache.SqliteCache` for WSDL parse caching (avoids re-fetching WSDL on every sync)
- Batch product fetches (50 at a time) to avoid supplier rate limits
- Individual product failures don't abort the entire sync

### Implementation
See the full code in the earlier plan session — `PromoStandardsClient` class with:
- `get_sellable_product_ids()`
- `get_product(product_id)`
- `get_products_batch(product_ids, batch_size=50)`
- `get_inventory(product_ids)`

This is the most complex task — requires understanding zeep's API, PromoStandards SOAP envelope structure, and XML response parsing.

---

## Task 4: Normalization Layer

**Priority:** After Task 1 (Urvashi), Task 2 (Sinchana), Task 3 (Vidhi + Tanishq) are all merged.
**File to create:** `backend/modules/promostandards/normalizer.py`
**Depends on:** All three parallel tasks must be done first.

### What this does
Maps PS SOAP response Pydantic models → canonical Product/ProductVariant/ProductImage DB rows via PostgreSQL upserts (`INSERT ... ON CONFLICT DO UPDATE`).

Three functions:
- `upsert_products()` — full sync
- `update_inventory_only()` — inventory-only (30-min cron)
- `update_pricing_only()` — pricing-only (daily cron)

---

## Task 6: E2E Verification

**Priority:** After Task 5 (Urvashi) is merged.
**Depends on:** Christian's SanMar API credentials.

Trigger `POST /api/sync/{sanmar_id}/products` → poll → verify products in catalog.

---

## PR Review Responsibilities

Review every PR from the interns before merge:
- **Sinchana PRs:** Task 0.3 (shadcn), Task 20 (terminology), Task 21 (supplier form), Task 2 (PS schemas)
- **Urvashi PRs:** Task 0.1 (port), Task 0.2 (dotenv), Task 22 (dashboard), Task 1 (schema), Task 5 (routes)
- **Vidhi PRs:** Task 0.4 (customers page), Task 0.5 (workflows page), Task 3 (resolver)

---

## Chase Christian For

- [ ] SanMar API credentials (blocks Task 6)
- [ ] OPS Postman collection export (blocks V1c)
- [ ] OPS API Client ID + Secret for n8n (blocks testing the OnPrintShop node)
- [ ] Phased SOW draft (committed in meeting)
