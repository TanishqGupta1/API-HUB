# Task 3 — WSDL Resolver

**Completed by:** Vidhi
**Branch:** `Vidhi`
**Date:** 2026-04-17
**Status:** ✅ Done — all tests passed

---

## In Simple Words (For Everyone)

Imagine you need to call 994 different suppliers. Each supplier has a phone directory that lists all the services they offer — like "Product Catalog", "Inventory", "Pricing", "Media/Images". But every supplier has written the service names differently in their directory:

- SanMar writes: `"Product Data"`
- Another supplier writes: `"ProductData"` (no space)
- Another writes just: `"product"`

They all mean the exact same thing — but because the names are different, a computer would fail to match them.

**The WSDL Resolver solves this problem.** It reads whatever name the supplier used, normalizes it to one standard name, and returns the correct connection URL for that service.

Without this, every time we added a new supplier we would need to manually write code to handle their unique naming. With this, any supplier that follows the PromoStandards format works automatically.

---

## What is a WSDL URL?

WSDL stands for **Web Services Description Language**. It is a web address (URL) that tells our system exactly how to talk to a supplier's API — what to send, what to expect back, and how the connection works.

Example:
```
https://ws.sanmar.com/PromoStandardsService/PromoStandardsServicePort?wsdl
```

This URL is stored in our database (cached from the PromoStandards directory) for each supplier. The resolver finds the right one.

---

## Files Created

| File | Purpose |
|------|---------|
| `backend/modules/promostandards/__init__.py` | Empty file — marks the directory as a Python module |
| `backend/modules/promostandards/resolver.py` | The resolver — finds the correct WSDL URL from cached supplier endpoints |

---

## Why This Task Exists

The PromoStandards directory API returns a list of endpoints for each supplier. Each endpoint has:
- A **ServiceType** — what the service does (e.g. "Product Data")
- A **ProductionURL** — the WSDL address to connect to that service

**The problem:** 994+ suppliers all registered their services independently. There is no strict enforcement of naming. So we see things like:

| Supplier | How they wrote it |
|----------|------------------|
| SanMar | `"Product Data"` |
| Supplier B | `"ProductData"` |
| Supplier C | `"product"` |
| Supplier D | `"Inventory Levels"` |
| Supplier E | `"Inventory"` |
| Supplier F | `"inventorylevels"` |

All of these mean the same service. The resolver maps all variations to one canonical (standard) name so the rest of the system only needs to ask for `"product_data"` and always gets the right URL — no matter which supplier it is.

---

## How It Works — Step by Step

### Step 1 — The Alias Map

The resolver has a built-in dictionary that maps every known variation to a standard name:

| What supplier wrote | Standard name |
|--------------------|---------------|
| `"Product Data"` | `product_data` |
| `"ProductData"` | `product_data` |
| `"product"` | `product_data` |
| `"Inventory Levels"` | `inventory` |
| `"Inventory"` | `inventory` |
| `"inventorylevels"` | `inventory` |
| `"Product Pricing and Configuration"` | `ppc` |
| `"pricing"` | `ppc` |
| `"Media Content"` | `media` |
| `"mediacontent"` | `media` |

---

### Step 2 — Normalize Function

Before looking anything up, both the search term and the supplier's text are cleaned:
1. Remove extra spaces from start and end
2. Convert to lowercase

So `"  Product Data  "` becomes `"product data"` → which maps to `"product_data"`.
And `"ProductData"` becomes `"productdata"` → which also maps to `"product_data"`.

Both end up at the same standard name. ✅

---

### Step 3 — Search and Return

The resolver loops through the supplier's cached endpoint list. For each endpoint:
1. Read the `ServiceType` field (or `Name` field if `ServiceType` is missing — some suppliers use different keys)
2. Normalize it
3. Compare to what we're looking for
4. If it matches → return the `ProductionURL`
5. If nothing matches after checking all endpoints → return `None`

---

## The Code

```python
# backend/modules/promostandards/resolver.py

_SERVICE_TYPE_ALIASES = {
    "product data": "product_data",
    "productdata": "product_data",
    "product": "product_data",
    "inventory": "inventory",
    "inventory levels": "inventory",
    "inventorylevels": "inventory",
    "product pricing and configuration": "ppc",
    "ppc": "ppc",
    "pricing": "ppc",
    "pricing and configuration": "ppc",
    "media content": "media",
    "mediacontent": "media",
    "media": "media",
}


def _normalize_service_type(raw: str) -> str:
    return _SERVICE_TYPE_ALIASES.get(raw.strip().lower(), raw.strip().lower())


def resolve_wsdl_url(endpoint_cache: list[dict], service_type: str) -> str | None:
    target = _normalize_service_type(service_type)
    for ep in endpoint_cache or []:
        raw_type = ep.get("ServiceType") or ep.get("Name") or ""
        if _normalize_service_type(raw_type) == target:
            url = ep.get("ProductionURL")
            if url:
                return url
    return None
```

---

## Tests & Verification

All 9 tests were run inside the live Docker container and passed.

### Test 1 — Standard supplier naming

```
Ask for "product_data" → returns correct SanMar product data URL   ✅
Ask for "inventory"    → returns correct SanMar inventory URL       ✅
Ask for "ppc"          → returns correct SanMar pricing URL         ✅
Ask for "media"        → returns correct SanMar media URL           ✅
```

**What this proves:** The core function works. Given normal supplier data, it finds and returns the right URL.

---

### Test 2 — Inconsistent supplier naming

```
Supplier used "ProductData" (no space) → still found as "product_data"   ✅
Supplier used "Name" field instead of "ServiceType" field → still found  ✅
```

**What this proves:** The resolver handles real-world naming inconsistencies across different suppliers automatically.

---

### Test 3 — Safe edge cases (nothing crashes)

```
Asked for a service that doesn't exist    → returns None, no crash   ✅
Empty endpoint list passed                → returns None, no crash   ✅
None passed instead of a list             → returns None, no crash   ✅
```

**What this proves:** The resolver is safe to use in all situations. It never crashes — it simply returns `None` when it cannot find what was asked for, and the calling code can handle that gracefully.

---

### Test output

```
All tests passed!
```

---

## Where This Fits in the Pipeline

```
PromoStandards Directory API
        │
        ▼
Supplier endpoint cache (stored in database)
        │
        ▼
  WSDL Resolver  ◀── YOU ARE HERE (Task 3)
        │
        ▼
   SOAP Client (Task 3 — next part / Sinchana's Task 2)
        │
        ▼
  Normalizer (Task 4 — blocked until Tasks 1, 2, 3 all done)
        │
        ▼
  Sync Endpoints (Task 5)
        │
        ▼
  Full pipeline running
```

---

## What Is Still Needed Before the Pipeline Can Run

This task (Task 3) is one of three parallel tasks in V1a. All three must be done before Task 4 (Normalizer) can start:

| Task | Owner | Status |
|------|-------|--------|
| Task 1 — Schema Updates (add unique constraints, ProductImage model) | Urvashi | ⬜ TODO |
| Task 2 — PromoStandards Response Schemas (typed Pydantic models) | Sinchana | ⬜ TODO |
| **Task 3 — WSDL Resolver** | **Vidhi** | **✅ DONE** |

Once Tasks 1 and 2 are complete, Task 4 (Normalizer) can begin.
