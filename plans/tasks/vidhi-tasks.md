# Vidhi — Sprint Tasks

**Status:** 6/6 tasks shipped ✅ Sprint complete.
**Branch:** `Vidhi` — all completed work pushed to remote

---

## ✅ Completed

- **Task 0.4** — Customers (Storefronts) page with list + OAuth2 credential form (`frontend/src/app/customers/page.tsx`) — commit `e1156ec`
- **Task 0.5** — Workflows page with animated pipeline visualizer (`frontend/src/components/workflows/pipeline-view.tsx`) — commit `8985dc6`
- **Task 3** — WSDL Resolver (`backend/modules/promostandards/resolver.py`) — commit `4b18c15` — all 9 tests passed
- **Task 13** — OPS Image Pipeline (`backend/modules/ops_push/image_pipeline.py` + `routes.py`) — commit `ce9837d` — E2E tested: download → resize 800×800 → WebP q85 → served at `GET /api/push/image/{image_id}/processed`
- **Task 14** — 4Over REST + HMAC Client (`backend/modules/rest_connector/fourover_client.py`) — all 9 unit tests passed (signature format + MockTransport request verification). E2E against real 4Over sandbox blocked on Christian's credentials.
- **Task 15** — 4Over Normalizer (`backend/modules/rest_connector/fourover_normalizer.py`) — commit `44033bb` — all 7 unit tests passed + 9 Task 14 regression tests still passing. Extends `PSProductPart` with a backward-compatible `attributes: dict[str, str] = {}` field for 4Over's print-specific variant axes. Reads the user's saved Field Mapping config from `supplier.field_mappings["mapping"]`.

---

## Pending Tasks

### Task 3: WSDL Resolver *(✅ COMPLETED — commit `4b18c15`)*

**Priority:** **DO THIS FIRST.** Blocks Tanishq's SOAP client (Task 3b) which blocks every V1a downstream task.
**File to create:** `backend/modules/promostandards/resolver.py`

### What this does
PromoStandards directory returns endpoint lists where each endpoint has a `ServiceType` like "Product Data", "Inventory Levels", etc. Different suppliers register with inconsistent names ("Product Data" vs "ProductData"). Your resolver normalizes those strings and returns the right `ProductionURL` for each service type.

### Steps

- [x] **Step 1:** The `backend/modules/promostandards/` directory already exists (Sinchana created it for Task 2). Confirm with `ls backend/modules/promostandards/` — you should see `__init__.py` and `schemas.py`.
- [x] **Step 2:** Create `backend/modules/promostandards/resolver.py`:

```python
"""Resolve WSDL URLs from cached PromoStandards directory endpoints."""

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

- [x] **Step 3:** Sanity-check:
```bash
cd backend && source .venv/bin/activate
python -c "
from modules.promostandards.resolver import resolve_wsdl_url
eps = [
    {'ServiceType': 'Product Data', 'ProductionURL': 'https://ws.sanmar.com/pd?wsdl'},
    {'ServiceType': 'Inventory Levels', 'ProductionURL': 'https://ws.sanmar.com/inv?wsdl'},
]
assert resolve_wsdl_url(eps, 'product_data') == 'https://ws.sanmar.com/pd?wsdl'
assert resolve_wsdl_url(eps, 'inventory') == 'https://ws.sanmar.com/inv?wsdl'
assert resolve_wsdl_url([{'ServiceType': 'ProductData', 'ProductionURL': 'x'}], 'product_data') == 'x'
assert resolve_wsdl_url([], 'product_data') is None
print('resolver OK')
"
```

- [x] **Step 4:** Commit: `feat: WSDL resolver — maps PS ServiceType strings to ProductionURL with alias normalization` — commit `4b18c15` ✅

---

### Task 13: Image Pipeline *(✅ COMPLETED — commit `ce9837d`)*

**Priority:** After Task 3. Independent of all SOAP work.
**Files to create:**
- `backend/modules/ops_push/__init__.py`
- `backend/modules/ops_push/image_pipeline.py`
- Route added to `backend/modules/ops_push/routes.py`
**Dependencies:** `Pillow`, `httpx` (both already in requirements.txt)

### What this does
When n8n pushes a product to OPS, it needs images in the right size/format. This service downloads a supplier's image URL, resizes to 800×800, converts to WebP quality 85, and returns the processed bytes.

### Function signature

```python
async def process_image(source_url: str) -> bytes:
    """Download, resize to 800×800, convert to WebP q85. Returns bytes."""
```

### Endpoint

```
GET /api/push/image/{image_id}/processed
```
Loads the `ProductImage` row, calls `process_image(image.url)`, returns the WebP bytes with `Content-Type: image/webp`.

### Steps

- [x] **Step 1:** Create `backend/modules/ops_push/__init__.py` (empty) and `image_pipeline.py`:
```python
from io import BytesIO
import httpx
from PIL import Image

async def process_image(source_url: str) -> bytes:
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.get(source_url)
        r.raise_for_status()
    img = Image.open(BytesIO(r.content)).convert("RGB")
    img.thumbnail((800, 800), Image.Resampling.LANCZOS)
    out = BytesIO()
    img.save(out, format="WEBP", quality=85)
    return out.getvalue()
```

- [x] **Step 2:** Create `routes.py` with the endpoint. Stream the bytes via FastAPI `Response(content=..., media_type="image/webp")`. Cache headers: `Cache-Control: public, max-age=86400`.
- [x] **Step 3:** Register the router in `backend/main.py`.
- [x] **Step 4:** Manual test:
```bash
curl -o test.webp http://localhost:8000/api/push/image/{some_image_id}/processed
file test.webp  # should say "RIFF ... WEBP"
```
Verified: `file` output → `RIFF (little-endian) data, Web/P image, VP8 encoding, 100x100`. Also tested live in Chrome — returned WebP pig image ✅
- [x] **Step 5:** Commit: `feat: OPS image pipeline — download, resize 800×800, WebP q85` — commit `ce9837d` ✅

---

### Task 14: 4Over REST + HMAC Client *(✅ COMPLETED)*

**Priority:** After Task 3. Blocked on Christian providing 4Over sandbox credentials for E2E — but the client code can be written and unit-tested independently against sample fixtures.
**File to create:** `backend/modules/rest_connector/fourover_client.py`

### What this does
4Over uses HMAC-SHA256 request signing. Every request must include `Authorization: hmac <api_key>:<signature>` where `signature = HMAC-SHA256(private_key, method + path + timestamp)`. You'll build `FourOverClient` using httpx.

### Class skeleton

```python
import hmac
import hashlib
import time
from datetime import datetime, timezone
import httpx

class FourOverClient:
    def __init__(self, base_url: str, auth_config: dict):
        self.base_url = base_url.rstrip("/")
        self.api_key = auth_config["api_key"]
        self.private_key = auth_config["private_key"].encode()

    def _sign(self, method: str, path: str) -> dict:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = f"{method}{path}{timestamp}".encode()
        sig = hmac.new(self.private_key, payload, hashlib.sha256).hexdigest()
        return {
            "Authorization": f"hmac {self.api_key}:{sig}",
            "X-Timestamp": timestamp,
        }

    async def get_categories(self) -> list[dict]: ...
    async def get_products(self) -> list[dict]: ...
    async def get_product_options(self, product_uuid: str) -> dict: ...
    async def get_quote(self, product_uuid: str, options: dict) -> dict: ...
```

### Steps
- [x] **Step 1:** Created `rest_connector/__init__.py` (directory didn't exist yet — Urvashi hadn't started Task 8).
- [x] **Step 2:** Implemented the class + 4 methods using httpx `AsyncClient`. Added input validation in the constructor, an injectable `timestamp` parameter on `_sign()` for deterministic testing, and an optional `http_client` parameter on every method so tests can pass a `MockTransport`-backed client.
- [x] **Step 3:** Wrote `backend/test_fourover_client.py` with 9 tests covering: known-vector HMAC-SHA256 signature check, determinism, method/path sensitivity, constructor validation, trailing-slash stripping, signed request via `httpx.MockTransport`, UUID embedded in options path, POST body for quote, and 401 error propagation. All 9 pass.
- [x] **Step 4:** Commit: `feat: 4Over REST+HMAC client with SHA-256 request signing`

---

### Task 15: 4Over Normalizer (Reuses Field Mapping UI) *(✅ COMPLETED — commit `44033bb`)*

**Priority:** After Task 14.
**File to create:** `backend/modules/rest_connector/fourover_normalizer.py`

### What this does
4Over products have paper types, coatings, folds — not colors and sizes. You built the Field Mapping UI in V0 Task 16; this is the backend half. It reads the field-mapping config from the DB (keyed by `supplier_id`) and applies transforms to map 4Over JSON → `PSProductData` format (same schemas as SanMar).

### Why reuse PSProductData?
The existing upsert logic (from Tanishq's Task 4 normalizer) consumes `PSProductData`. Outputting the same shape means the DB layer works unchanged for all 4 supplier types.

### Steps
- [x] **Step 1:** Checked how the Field Mapping UI stores config. Frontend PUTs `{mapping: {source: target}}` to `/api/suppliers/{id}/mappings`. Backend stores the body verbatim in `supplier.field_mappings` (JSONB column on `suppliers` table — already exists at `models.py:26`, route at `routes.py:92`).
- [x] **Step 2:** No new mapping table needed — `Supplier.field_mappings` JSONB column already in place. The normalizer reads `field_mappings["mapping"]` directly.
- [x] **Step 3:** Built `normalize_4over(raw_products, field_mapping, *, variants_key="variants") -> list[PSProductData]` in `backend/modules/rest_connector/fourover_normalizer.py`. Chose the cleaner "extend `PSProductPart` with `attributes: dict[str, str] = {}`" path — default empty dict keeps Sinchana's SanMar normalizer fully backward-compatible. Unmapped variant fields (coating, paper_weight, fold, finish) are packed into `attributes` so nothing is silently dropped.
- [x] **Step 4:** Wrote `backend/test_fourover_normalizer.py` with 7 offline tests: happy path with 3 realistic 4Over products + full mapping, attributes packing for unmapped fields, silent skip for products missing a mapped SKU, partial-mapping graceful defaults, empty input, SanMar-style `PSProductPart` regression guard on the new schema field, and type validation. All 7 pass. Task 14's 9 client tests still pass too (ran both).
- [x] **Step 5:** Commit: `feat: 4Over → PSProductData normalizer using Field Mapping config` — commit `44033bb` ✅

### Note
Task 16 (sync route HMAC branch) is Urvashi's — you coordinate by agreeing on the `PSProductData` output shape.
