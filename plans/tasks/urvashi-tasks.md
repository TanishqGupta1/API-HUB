# Urvashi — Sprint Tasks

**Status:** 4/5 V0/V1a sprint tasks shipped. Task 5 (sync routes) still pending — blocked on Vidhi's Task 3 + Tanishq's Tasks 3b + 4. Three new tasks added below for V1b + V1c.
**Branch:** `urvashi-sprint-v1` (mostly merged) → `urvashi-sprint-v2` for new work

---

## ✅ Completed

- **Task 0.1** — Postgres port reverted to `5432:5432` in `docker-compose.yml`
- **Task 0.2** — `load_dotenv` path fixed in `backend/database.py` and `seed_demo.py`
- **Task 22** — Dashboard wired to `/api/stats` + `/api/sync-jobs` (also covers V0.6)
- **Task 1** — Schema updates: `UniqueConstraint`s on Product + Variant, `category`, `ops_product_id`, `ProductImage` model

---

## Pending Tasks

### Task 5: Sync Trigger Endpoints *(BLOCKED — waiting on Vidhi T3 + Tanishq T3b/T4)*

**Priority:** Start as soon as Tanishq's Task 4 (normalizer) is merged. You can draft the route file now against the expected imports; it just won't run until the upstream pieces land.
**Files:**
- Create: `backend/modules/promostandards/routes.py`
- Modify: `backend/main.py` — one import + one `include_router` call

### What this does
FastAPI endpoints n8n calls to trigger syncs. Returns `202 Accepted` with a job ID; actual SOAP work runs as a background task.

### Endpoints
```
POST /api/sync/{supplier_id}/products
POST /api/sync/{supplier_id}/inventory
POST /api/sync/{supplier_id}/pricing
GET  /api/sync/{supplier_id}/status
```

*(Full reference implementation was included in the v1 sprint plan — see the archived version of this file or the V1 plan at `plans/2026-04-16-v1-integration-pipeline.md` Task 5. Code unchanged.)*

### Steps
- [ ] Confirm Vidhi's `resolver.py` and Tanishq's `client.py` + `normalizer.py` exist before implementing.
- [ ] Create routes.py importing from `.client`, `.normalizer`, `.resolver`.
- [ ] Register router in `main.py`.
- [ ] Verify `http://localhost:8000/docs` shows the sync endpoints.
- [ ] Commit: `feat: sync trigger endpoints — POST /api/sync/{supplier_id}/products|inventory|pricing`

---

### Task 7: Alphabroder Supplier Row

**Priority:** 10 minutes of work, do anytime.
**File:** via API call — but also add to `backend/seed_demo.py` so future fresh setups include it.

### What this does
Alphabroder is PromoStandards-compliant. No code needed — just create a DB row. Demonstrates the "suppliers are config, not code" principle.

### Steps
- [x] **Step 1:** Alphabroder already present in `seed_demo.py`; updated to match spec — proper case name, placeholder credentials, `is_active=False`. Kept `protocol="soap"` for consistency with SanMar's seed entry (sync routes accept both "soap" and "promostandards").
- [x] **Step 2:** Row updated in live DB via script against `async_session` (seed script skips existing rows). Verified via `GET /api/suppliers` and `POST /api/sync/.../products` returns 409 "not active" as expected.
- [x] **Step 3:** Commit: `feat: add Alphabroder supplier row (PromoStandards, zero code)`

---

### Task 8: S&S Activewear REST Adapter

**Priority:** After Task 7. Independent of V1a — has its own protocol path.
**Files to create:**
- `backend/modules/rest_connector/__init__.py`
- `backend/modules/rest_connector/client.py` (the `RESTConnectorClient` class)

**Coordination:** Sinchana owns the S&S → PSProductData mapping (Task 8a, `ss_normalizer.py`). You own the HTTP client.

### What this does
S&S Activewear API: `https://api.ssactivewear.com/V2`, HTTP Basic Auth (account number + API key from `supplier.auth_config`).

### Class skeleton
```python
import httpx

class RESTConnectorClient:
    def __init__(self, base_url: str, auth_config: dict):
        self.base_url = base_url.rstrip("/")
        self.auth = (auth_config["account_number"], auth_config["api_key"])

    async def get_products(self) -> list[dict]:
        async with httpx.AsyncClient(auth=self.auth, timeout=60.0) as c:
            r = await c.get(f"{self.base_url}/Products/")
            r.raise_for_status()
            return r.json()

    async def get_styles(self) -> list[dict]: ...
    async def get_categories(self) -> list[dict]: ...
```

### Sync route branching
In `modules/promostandards/routes.py` (Task 5), add a `supplier.protocol` branch:
```python
if supplier.protocol == "promostandards":
    # existing SOAP path
elif supplier.protocol == "rest":
    client = RESTConnectorClient(supplier.auth_config["base_url"], supplier.auth_config)
    raw = await client.get_products()
    ps_products, inv, price, media = ss_to_ps_format(raw)  # Sinchana's mapper
    await upsert_products(db, supplier_id, ps_products, inv, price, media)
```

### Steps
- [ ] Implement `RESTConnectorClient` with 3 methods.
- [ ] Coordinate with Sinchana on the fixture JSON she'll use for testing `ss_to_ps_format`.
- [ ] Extend the sync route (Task 5) with the `rest` branch — hand-merge with Vidhi's 4Over branch (Task 16) to avoid conflicts.
- [ ] Commit: `feat: S&S Activewear REST client with HTTP Basic Auth`

---

### Task 11: Markup Rule Execution Engine

**Priority:** Unblocked — start anytime. Independent of all sync work.
**File to create:** `backend/modules/markup/engine.py`
**Endpoint to add:** `GET /api/push/{customer_id}/product/{product_id}/payload`

### What this does
Applies customer-specific markup rules to a product's variants and returns the final OPS-ready payload. n8n calls this endpoint before invoking `setProduct` on each product.

### Rule resolution order (first match wins, sorted by `priority desc`)
1. `scope = "product:{supplier_sku}"` — product-level override
2. `scope = "category:{category_name}"`
3. `scope = "all"` — global default

### Calculation
```python
markup_price = base_price * (1 + markup_pct / 100)
if min_margin and markup_price < base_price * (1 + min_margin / 100):
    markup_price = base_price * (1 + min_margin / 100)
if rounding == "nearest_99":
    markup_price = floor(markup_price) + Decimal("0.99")
elif rounding == "nearest_dollar":
    markup_price = Decimal(round(markup_price))
```

### Function signature
```python
async def calculate_price(
    db: AsyncSession, customer_id: UUID, product_id: UUID
) -> dict:
    """Return {product: {...}, variants: [{sku, color, size, final_price, ...}], ...}"""
```

### Endpoint response shape
```json
{
  "product": {"supplier_sku": "PC61", "name": "...", "brand": "...", "category": "T-Shirts"},
  "variants": [{"sku": "PC61-NVY-M", "color": "Navy", "size": "M", "base_price": 3.99, "final_price": 5.99}],
  "images": [{"url": "...", "image_type": "front"}]
}
```

### Steps
- [ ] **Step 1:** Write the rule resolution logic (query `markup_rules` table, order by priority desc, first match wins).
- [ ] **Step 2:** Write `calculate_price` — load product + variants + images + applicable rule, apply math, return the dict.
- [ ] **Step 3:** Add the route to `backend/modules/markup/routes.py` (or a new `backend/modules/ops_push/routes.py` if Vidhi creates it for Task 13).
- [ ] **Step 4:** Write a pytest with 3 scenarios: global rule only, category override, product override. Verify precedence.
- [ ] **Step 5:** Commit: `feat: markup engine + push payload endpoint for n8n OPS push`
