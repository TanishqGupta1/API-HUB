# SanMar PromoStandards Smoke Test — Design

**Date:** 2026-04-23
**Status:** Draft — awaiting user approval
**Owner:** tanishq@printdeed.com

## Goal

Verify the existing `PromoStandardsClient` works against real SanMar production SOAP endpoints for a handful of known SKUs (PC61, K420, LPC61, MM1000). Scope is deliberately narrow: auth + WSDL reachable + parser handles SanMar-specific response shapes. No full catalog sync. No SFTP. No DB writes on first pass.

Reference: `sanmar/SanMar-Web-Services-Integration-Guide-24.3.pdf` (pages 40–86).

## Non-Goals

- Full catalog pull via `getProductSellable` → `getProduct` batch (thousands of SKUs)
- Bulk SFTP ingestion (covered by separate plan `2026-04-22-sanmar-sftp-integration-design.md`)
- SanMar proprietary (non-PromoStandards) services: Standard Product Info, SanMar Inventory, SanMar Pricing, Invoicing, License Plate
- Invoice / Order Status / Shipment Notification PromoStandards services
- Frontend UI changes
- Scheduled sync / n8n workflow

## Known Deviations — Existing Client vs SanMar PromoStandards Spec

The PDF revealed required parameters and response shapes that the current `backend/modules/promostandards/client.py` does not handle. These are **PromoStandards spec requirements**, not SanMar quirks — fixes benefit every PS supplier.

### Product Data V2.0.0

| Issue | Current client | Required by SanMar / PS spec |
|-------|----------------|------------------------------|
| Auth missing locale | `_auth()` sends `wsVersion`, `id`, `password` only | Must also send `localizationCountry="us"`, `localizationLanguage="en"` |
| Category field name | Parser reads `categoryName` or `name` | SanMar response uses `<category>` and `<subCategory>` inside `<ProductCategory>` |
| Description parsing | Grabs single string | SanMar returns multiple `<description>` elements — must join or concat |
| Product response root | Reads `.Product` | SanMar wraps in `<ns2:GetProductResponse>` → `<ns2:Product>` (zeep likely strips ns2 but worth verifying) |

**WSDL:**
- Prod: `https://ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl`
- Test: `https://test-ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl`

### Media Content V1.1.0

| Issue | Current client | Required |
|-------|----------------|----------|
| Wrong default version | `ws_version="1.0.0"` | Must be `"1.1.0"` — request will fail on 1.0.0 |
| Missing required param | No `mediaType` argument | `mediaType` is required, value `"Image"` or `"Document"` |
| Missing optional params | — | `cultureName`, `classType` (1004 Swatch, 1006 Primary, 1007 Front, 1008 Rear, 2001 High) |

**WSDL:**
- Prod: `https://ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl`
- Test: `https://test-ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl`

### Inventory V2.0.0

| Issue | Current client | Required |
|-------|----------------|----------|
| Wrong response path | Reads `Inventory.ProductVariationInventoryArray.ProductVariationInventory` | SanMar uses `Inventory.PartInventoryArray.PartInventory` |
| Wrong quantity path | `part.quantityAvailable` or `.quantity` | `part.quantityAvailable.Quantity.value` (nested `<Quantity>` with `<uom>EA</uom>` and `<value>1045</value>`) |
| Wrong cap | Hardcoded 500 | SanMar caps at 3000 per warehouse. PS spec does not mandate 500 — remove hardcode or make supplier-configurable |
| Per-warehouse qty lost | Only takes first `InventoryLocation.name` | Each `<InventoryLocation>` has its own `<inventoryLocationQuantity><Quantity><value>N</value>...</Quantity></inventoryLocationQuantity>`. Needs separate `PSInventoryLevel` per location or new `warehouse_breakdown` field |

**WSDL:**
- Prod: `https://ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL`
- Test: `https://test-ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL`

### Pricing and Configuration V1.0.0

| Issue | Current client | Required |
|-------|----------------|----------|
| Missing required params | `getConfigurationAndPricing(productId=pid, **_auth)` | Also needs: `currency="USD"`, `fobId` (1–7, 12, or 31), `priceType` ("Net", "List", or "Customer"), `localizationCountry="US"`, `localizationLanguage="EN"`, `configurationType="Blank"` |
| maxQuantity field | Reads `maxQuantity`/`quantityMax` | SanMar PPC does not return `maxQuantity`. Uses `priceEffectiveDate` + `priceExpiryDate` instead |

**WSDL:**
- Prod: `https://ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL`
- Test: `https://test-ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL`

## Architecture

```
backend/scripts/sanmar_smoke.py           ← new; standalone runner
        │
        ▼
backend/modules/promostandards/client.py  ← patched (see fixes above)
        │
        ├─► SanMar Product Data WSDL   (getProductSellable, getProduct)
        ├─► SanMar Inventory WSDL      (getInventoryLevels)
        ├─► SanMar Media WSDL          (getMediaContent)
        └─► SanMar PPC WSDL            (getConfigurationAndPricing)
```

**Credentials path (per project constraint "credentials via UI, encrypted in DB"):**

```
User → /suppliers page → POST /api/suppliers → EncryptedJSON column → DB
                                                      │
                                                      ▼
              scripts/sanmar_smoke.py ──► load Supplier row by slug ──► auth_config{id, password}
```

## Components

### 1. Client patches — `backend/modules/promostandards/client.py`

- **`_auth()`**: accept optional `localization_country`, `localization_language` kwargs; default to `"us"` / `"en"`. Include in returned dict only for services that need them (Product Data, PPC).
- **`_parse_product()`**: change category extraction to read `category` (fallback to `categoryName`, `name`). Join all `<description>` elements into a single newline-separated string.
- **`get_media()`**: change default `ws_version="1.1.0"`. Add required `media_type` parameter. Pass through to zeep call.
- **`_sync_get_inventory()` + `_parse_inventory()`**: update response path to `PartInventoryArray` → `PartInventory`. Update quantity extraction to drill `quantityAvailable.Quantity.value`. Remove hardcoded 500 cap (use supplier-configurable cap or drop entirely — SanMar reports up to 3000 per warehouse). For this smoke test, aggregate per-warehouse quantities into a single `PSInventoryLevel` per part (sum of all `inventoryLocationQuantity.Quantity.value`) and record the highest-stock warehouse in `warehouse_code`. Multi-warehouse breakdown is a deferred follow-up (Open Question 5).
- **`_sync_get_pricing()`**: accept and pass new required params. Default `fob_id=1` (Seattle), `price_type="Net"`, `currency="USD"`, `configuration_type="Blank"`, locale `US`/`EN`.
- **`PSInventoryLevel`** schema: consider adding `warehouse_name` alongside `warehouse_code`, or changing semantics so each level represents one warehouse's stock for one part. Normalizer callers need review when this changes.

All changes must preserve supplier-agnostic behavior — no SanMar strings in the client.

### 2. Supplier row creation — via UI

Steps (user, one-time):

1. Start stack: `docker compose up -d postgres n8n` + `uvicorn main:app --reload`
2. Frontend: `cd frontend && npm run dev`
3. Visit `http://localhost:3000/suppliers`, click "Add supplier"
4. Fields:
   - `name = "SanMar"`
   - `slug = "sanmar"`
   - `protocol = "promostandards"`
   - `promostandards_code = "SANM"`
   - `auth_config = {"id": "<SanMar.com username>", "password": "<SanMar.com password>"}`
   - `is_active = true`
5. **Manually seed `endpoint_cache`** via a one-off SQL update or PATCH call, since PS directory lookup for SanMar may not match our resolver aliases until verified. Shape:
   ```json
   [
     {"ServiceType": "Product Data", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl"},
     {"ServiceType": "Inventory Levels", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL"},
     {"ServiceType": "Media Content", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl"},
     {"ServiceType": "Product Pricing and Configuration", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL"}
   ]
   ```

### 3. Smoke script — `backend/scripts/sanmar_smoke.py`

New file. Responsibilities:

- Load SanMar `Supplier` by slug from DB (uses existing async session)
- Decrypt `auth_config` via existing `EncryptedJSON` column type
- Instantiate four `PromoStandardsClient` instances (one per WSDL) using hardcoded SanMar prod URLs from the PDF
- For a curated SKU list (default: `["PC61", "K420", "LPC61", "MM1000"]`, CLI-overridable):
  - Call `get_product(sku)` — print `product_id`, `product_name`, `brand`, first 3 categories, part count
  - Call `get_inventory([sku])` — print aggregate `quantity_available` and primary `warehouse_code` per part. For diagnostic visibility the script also logs the raw zeep response element count (number of `InventoryLocation` entries) so we can confirm 8 warehouses were present pre-aggregation.
  - Call `get_media([sku], media_type="Image")` — print URL count, first 3 URLs with class types
  - Call `get_pricing([sku])` — print Net price for fobId=1, minQuantity=1
- Exit 0 on all-success, 1 on any auth/WSDL/parse failure
- Accept `--test` flag to use `test-ws.sanmar.com` endpoints instead of prod

No DB writes. No normalizer invocation. Script is idempotent and safe to re-run.

## Data Flow

```
1. User inputs creds via UI           → Supplier row encrypted in DB
2. User runs `python scripts/sanmar_smoke.py`
3. Script queries DB for 'sanmar'     → decrypted auth_config
4. For each SKU in fixed list:
     Script → zeep → SanMar prod WSDL → XML response
     zeep   → parsed objects           → client parser → Pydantic model
     Pydantic model                    → pretty-printed to stdout
5. Script exits 0 if all SKUs pass, 1 otherwise
```

## Error Handling

- **Auth failure** — SOAP fault `"ERROR: User authenticating failed"` per PDF pg 7. Script prints fault string and exits 1 immediately (do not continue with more SKUs — creds are wrong).
- **WSDL unreachable** — zeep raises `TransportError` or `requests.exceptions.ConnectionError`. Script prints `service=<name> url=<wsdl>` and exits 1.
- **Parse failure on one SKU** — log warning, continue remaining SKUs. Report summary at end: `3/4 SKUs passed`. Non-zero exit.
- **Empty response (0 parts, 0 inventory locations, 0 media)** — not a failure; print `[EMPTY]` and continue. Flag in summary.

## Testing

- **Unit tests** — new `backend/tests/test_client_sanmar_fixes.py` with canned SanMar XML responses (copied from the PDF examples) fed through zeep-style `SimpleNamespace` fixtures. Verifies:
  - Auth dict includes `localizationCountry` / `localizationLanguage` when requested
  - Product parser extracts `category` (not only `categoryName`)
  - Description parser joins multi-element descriptions
  - Media call sends `mediaType="Image"` and `wsVersion="1.1.0"`
  - Inventory parser reads `PartInventoryArray` → `PartInventory` → `quantityAvailable.Quantity.value`
  - Inventory aggregates per-warehouse `inventoryLocationQuantity.Quantity.value` into the single `PSInventoryLevel.quantity_available`
  - `warehouse_code` is the name/id of the highest-stock `InventoryLocation`
  - PPC call sends `currency`, `fobId`, `priceType`, `localizationCountry`, `localizationLanguage`, `configurationType`
- **Regression** — run existing `test_client.py` / `test_normalizer.py` / `test_sync_routes.py`; they must still pass (no behavior change for Port & Company–style fixtures).
- **Smoke run** — manual. Real network. Documented pass criteria below.

## Pass Criteria

Smoke script with real SanMar credentials against prod must produce, for SKU `PC61`:

- `get_product`: non-empty `product_name`, `brand`, ≥1 category, ≥1 part with color and size populated
- `get_inventory`: ≥1 part with ≥1 warehouse quantity ≥ 0 (zero is valid)
- `get_media`: ≥1 URL starting with `https://cdnm.sanmar.com` or `https://cdnl.sanmar.com`
- `get_pricing`: ≥1 part with `price > 0`, `priceUom` in `{PC, DZ, CA, ...}`

All four SKUs must pass, or the script exits non-zero and we iterate on parser fixes.

## Risks / Open Questions

1. **zeep namespace handling** — SanMar responses prefix elements with `ns2:`. zeep typically strips namespaces when returning Python objects, but `xsi:type="ns2:Inventory"` patterns (see PDF pg 62) can confuse zeep. If parsing fails with `AttributeError` on `.Inventory`, we may need to add `wsse` or xsd settings.
2. **WSDL URL discrepancy** — PDF lists `ProductDataServiceV2.xml?wsdl` (with `.xml`) while the existing plan example used `ProductDataServiceBindingV2?WSDL`. Use PDF as authoritative source.
3. **`test-ws.sanmar.com` availability** — PDF warns test env "may be unavailable during internal updates". Prod is the primary target; test env is optional fallback.
4. **Rate limits** — PDF pg 14 says "Best Practices" section covers this. Not read yet. If smoke hits a rate limit on 4 SKUs × 4 services = 16 calls, we'll pace calls with `asyncio.sleep(0.5)` between each.
5. **`PSInventoryLevel` schema change** — emitting one row per warehouse changes the contract for `update_inventory_only()` normalizer. Either (a) keep top-level aggregate in a new field and leave per-warehouse out of scope, or (b) plan a follow-up to update the normalizer. Pick (a) for this smoke test — aggregate the per-warehouse quantities into one `quantity_available` and pick a "primary" warehouse (highest-stock) for `warehouse_code`.

## Out of Scope for This Spec — Deferred Follow-Ups

- Wire fixed client into route path (`POST /api/sync/:id/products`) — after smoke passes
- Run full catalog sync — after route path validated against SanMar
- Add SanMar to PS directory cache automatically via existing `get_cached_endpoints` flow — if PS directory lookup doesn't return SanMar, add a manual override path
- Multi-warehouse inventory breakdown in DB schema — future plan
- `getProductCloseOut` and `getProductDateModified` — delta-sync plan (V1e)
