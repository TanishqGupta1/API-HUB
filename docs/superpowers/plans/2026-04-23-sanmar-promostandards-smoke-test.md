# SanMar PromoStandards Smoke Test — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Patch the existing supplier-agnostic `PromoStandardsClient` to match the PromoStandards spec fields SanMar requires, then ship a standalone smoke-test script that exercises four SanMar production WSDLs end-to-end for a curated SKU list.

**Architecture:** Six surgical patches to `backend/modules/promostandards/client.py` (no new files for the client itself) driven by TDD against the existing `FakeService` test harness, plus one new CLI script under `backend/scripts/` that loads the SanMar supplier row from the DB, instantiates four `PromoStandardsClient` instances (one per WSDL), and pretty-prints the results of getProduct / getInventoryLevels / getMediaContent / getConfigurationAndPricing for each SKU.

**Tech Stack:** Python 3.12, zeep 4.3, asyncio, pytest + pytest-asyncio, SQLAlchemy 2 async + asyncpg, PostgreSQL 16.

**Spec reference:** `docs/superpowers/specs/2026-04-23-sanmar-promostandards-smoke-test-design.md`
**PDF reference:** `sanmar/SanMar-Web-Services-Integration-Guide-24.3.pdf` (pages 40–86).

---

## File Structure

| Path | Status | Responsibility |
|------|--------|----------------|
| `backend/modules/promostandards/client.py` | **Modify** | Add locale params to `get_product`; fix `_parse_product` category + description parsing; change `get_media` default version + require `mediaType`; rewrite inventory quantity + warehouse parsing; add required PPC params |
| `backend/test_promostandards_client.py` | **Modify** | Update inventory cap expectation; add tests for each new behavior |
| `backend/scripts/__init__.py` | **Create** | Empty package marker so tests can import the script module |
| `backend/scripts/sanmar_smoke.py` | **Create** | CLI runner that loads SanMar creds + hits four WSDLs for N SKUs |
| `backend/tests/test_sanmar_smoke.py` | **Create** | Unit test for the script with mocked clients |
| `docs/sanmar_smoke_runbook.md` | **Create** | Manual steps: create Supplier row via UI, seed endpoint_cache, run script, interpret output |

Design note: all client patches stay behind default kwargs so existing S&S / Alphabroder / 4Over tests keep passing. No changes to `schemas.py`, `normalizer.py`, `routes.py`, or `resolver.py`.

---

## Task 1: Product Data locale parameters

SanMar `getProduct` requires `localizationCountry` and `localizationLanguage` in the SOAP body. The current client omits both. Calls against SanMar return a SOAP fault until this is fixed.

**Files:**
- Modify: `backend/modules/promostandards/client.py`
- Modify: `backend/test_promostandards_client.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/test_promostandards_client.py` after the existing `test_get_product_*` tests:

```python
async def test_get_product_sends_localization_defaults():
    """SanMar requires localizationCountry + localizationLanguage on getProduct."""
    svc = FakeService()
    svc.responses[("getProduct", "PC61")] = NS(
        Product=NS(productId="PC61", productName="Tee")
    )
    await _client(svc).get_product("PC61")
    _, kwargs = svc.calls[-1]
    assert kwargs["localizationCountry"] == "us"
    assert kwargs["localizationLanguage"] == "en"


async def test_get_product_accepts_explicit_locale():
    svc = FakeService()
    svc.responses[("getProduct", "PC61")] = NS(
        Product=NS(productId="PC61")
    )
    await _client(svc).get_product(
        "PC61", localization_country="ca", localization_language="fr"
    )
    _, kwargs = svc.calls[-1]
    assert kwargs["localizationCountry"] == "ca"
    assert kwargs["localizationLanguage"] == "fr"


async def test_get_products_batch_propagates_locale():
    svc = FakeService()
    svc.responses["getProduct"] = NS(Product=NS(productId="X"))
    await _client(svc).get_products_batch(["A", "B"])
    for _, kwargs in svc.calls:
        assert kwargs["localizationCountry"] == "us"
        assert kwargs["localizationLanguage"] == "en"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd api-hub/backend && source .venv/bin/activate
pytest test_promostandards_client.py::test_get_product_sends_localization_defaults -v
```

Expected: FAIL with `KeyError: 'localizationCountry'` — the current `getProduct` call doesn't pass the key.

- [ ] **Step 3: Patch `get_product` + `_sync_get_product`**

Open `backend/modules/promostandards/client.py`. Replace the existing `get_product` and `_sync_get_product` methods (around lines 155–167) with:

```python
    async def get_product(
        self,
        product_id: str,
        ws_version: str = "2.0.0",
        localization_country: str = "us",
        localization_language: str = "en",
    ) -> PSProductData | None:
        return await asyncio.to_thread(
            self._sync_get_product,
            product_id,
            ws_version,
            localization_country,
            localization_language,
        )

    def _sync_get_product(
        self,
        product_id: str,
        ws_version: str,
        localization_country: str,
        localization_language: str,
    ) -> PSProductData | None:
        svc = self._get_service()
        try:
            response = svc.getProduct(
                productId=product_id,
                localizationCountry=localization_country,
                localizationLanguage=localization_language,
                **self._auth(ws_version),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("getProduct(%s) failed: %s", product_id, exc)
            return None
        return self._parse_product(response)
```

- [ ] **Step 4: Patch `get_products_batch` + `_sync_fetch_batch`**

Replace the existing `get_products_batch` (around lines 169–183) and `_sync_fetch_batch` (around lines 185–199) with:

```python
    async def get_products_batch(
        self,
        product_ids: list[str],
        batch_size: int = 50,
        ws_version: str = "2.0.0",
        localization_country: str = "us",
        localization_language: str = "en",
    ) -> list[PSProductData]:
        """Fetch products in batches. Batch size is advisory — PS getProduct is
        one-at-a-time, so the batches only govern how often we yield to the
        loop."""
        out: list[PSProductData] = []
        for i in range(0, len(product_ids), batch_size):
            batch = product_ids[i : i + batch_size]
            results = await asyncio.to_thread(
                self._sync_fetch_batch,
                batch,
                ws_version,
                localization_country,
                localization_language,
            )
            out.extend(results)
        return out

    def _sync_fetch_batch(
        self,
        product_ids: list[str],
        ws_version: str,
        localization_country: str,
        localization_language: str,
    ) -> list[PSProductData]:
        svc = self._get_service()
        out: list[PSProductData] = []
        for pid in product_ids:
            try:
                response = svc.getProduct(
                    productId=pid,
                    localizationCountry=localization_country,
                    localizationLanguage=localization_language,
                    **self._auth(ws_version),
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("getProduct(%s) failed: %s", pid, exc)
                continue
            parsed = self._parse_product(response)
            if parsed is not None:
                out.append(parsed)
        return out
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd api-hub/backend && source .venv/bin/activate
pytest test_promostandards_client.py -v -k "get_product"
```

Expected: all `test_get_product_*` tests PASS, including the three new tests.

- [ ] **Step 6: Run the full client test suite for regression**

```bash
pytest test_promostandards_client.py -v
```

Expected: all pre-existing tests still PASS.

- [ ] **Step 7: Commit**

```bash
cd /Users/tanishq/Documents/project-files/api-hub/api-hub
git add backend/modules/promostandards/client.py backend/test_promostandards_client.py
git commit -m "feat(promostandards): add localizationCountry/Language params to getProduct"
```

---

## Task 2: Product parser — `category` field and multi-description join

SanMar's `<ProductCategory>` wraps `<category>` (not `<categoryName>`). Its `<description>` element is repeated — zeep returns a list when maxOccurs > 1. The current parser reads only the first description string and the wrong category field.

**Files:**
- Modify: `backend/modules/promostandards/client.py`
- Modify: `backend/test_promostandards_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/test_promostandards_client.py`:

```python
async def test_parse_product_reads_sanmar_category_field():
    """SanMar wraps category name in <category>, not <categoryName>."""
    svc = FakeService()
    svc.responses[("getProduct", "MM1000")] = NS(
        Product=NS(
            productId="MM1000",
            productName="Polo",
            ProductCategoryArray=NS(
                ProductCategory=[NS(category="Polos/Knits", subCategory="Cotton")]
            ),
        )
    )
    product = await _client(svc).get_product("MM1000")
    assert product is not None
    assert "Polos/Knits" in product.categories


async def test_parse_product_joins_multi_description():
    """SanMar returns several <description> elements; zeep yields a list."""
    svc = FakeService()
    svc.responses[("getProduct", "MM1000")] = NS(
        Product=NS(
            productId="MM1000",
            description=[
                "Crafted in heavier knit",
                "8.1-ounce fabric",
                "Moisture-wicking",
            ],
        )
    )
    product = await _client(svc).get_product("MM1000")
    assert product is not None
    assert product.description == (
        "Crafted in heavier knit\n8.1-ounce fabric\nMoisture-wicking"
    )


async def test_parse_product_single_description_still_works():
    """Backwards compat: suppliers returning one description string must still parse."""
    svc = FakeService()
    svc.responses[("getProduct", "PC61")] = NS(
        Product=NS(productId="PC61", description="100% cotton")
    )
    product = await _client(svc).get_product("PC61")
    assert product is not None
    assert product.description == "100% cotton"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test_promostandards_client.py -v -k "category_field or multi_description"
```

Expected: FAIL — `test_parse_product_reads_sanmar_category_field` returns `[]` for categories, and `test_parse_product_joins_multi_description` stringifies the whole list via `_text(list)` which yields `"['Crafted in heavier knit', ...]"`.

- [ ] **Step 3: Patch `_parse_product`**

Open `backend/modules/promostandards/client.py` and replace the `_parse_product` method (around lines 201–230) with:

```python
    def _parse_product(self, response: Any) -> PSProductData | None:
        product = _attr(response, "Product", "product") or response
        pid = _text(_attr(product, "productId", "product_id"))
        if not pid:
            return None

        cat_container = _attr(product, "ProductCategoryArray", "productCategoryArray")
        category_items = _as_list(_attr(cat_container, "ProductCategory", "productCategory"))
        categories: list[str] = []
        for c in category_items:
            # SanMar uses <category>; others use <categoryName> or <productCategory>.
            # Fall back to raw string if the element itself is a primitive.
            name = _text(
                _attr(c, "category", "categoryName", "productCategory", "name")
            ) or _text(c)
            if name:
                categories.append(name)

        # description may be a list (SanMar emits one element per line) or a
        # single string. Join lists with newlines.
        raw_description = _attr(product, "description")
        if isinstance(raw_description, list):
            parts = [_text(d) for d in raw_description]
            description = "\n".join(p for p in parts if p) or None
        else:
            description = _text(raw_description)

        parts_container = _attr(product, "productPartArray", "ProductPartArray")
        part_items = _as_list(_attr(parts_container, "productPart", "ProductPart"))
        parts = [p for p in (self._parse_part(item) for item in part_items) if p]

        return PSProductData(
            product_id=pid,
            product_name=_text(_attr(product, "productName", "name")),
            description=description,
            brand=_text(_attr(product, "productBrand", "brand")),
            categories=categories,
            product_type=_text(_attr(product, "productType")) or "apparel",
            primary_image_url=_text(_attr(product, "primaryImageURL", "primaryImageUrl")),
            parts=parts,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest test_promostandards_client.py -v -k "parse_product"
```

Expected: PASS for all three new tests plus the pre-existing `test_parse_product_*` tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/tanishq/Documents/project-files/api-hub/api-hub
git add backend/modules/promostandards/client.py backend/test_promostandards_client.py
git commit -m "fix(promostandards): support SanMar <category> field and multi-line <description>"
```

---

## Task 3: Media service — v1.1.0 default and required `mediaType`

SanMar's Media Content WSDL is `V1.1.0`, not `1.0.0`. The SOAP body requires a `mediaType` element (values: `Image`, `Document`). The current client defaults to `1.0.0` and omits `mediaType`, so every SanMar call errors.

**Files:**
- Modify: `backend/modules/promostandards/client.py`
- Modify: `backend/test_promostandards_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/test_promostandards_client.py`:

```python
async def test_get_media_uses_v110_and_sends_mediatype_image():
    """SanMar requires wsVersion=1.1.0 and mediaType field."""
    svc = FakeService()
    svc.responses[("getMediaContent", "PC61")] = NS(MediaContentArray=None)
    await _client(svc).get_media(["PC61"])
    _, kwargs = svc.calls[-1]
    assert kwargs["wsVersion"] == "1.1.0"
    assert kwargs["mediaType"] == "Image"


async def test_get_media_accepts_document_media_type():
    svc = FakeService()
    svc.responses[("getMediaContent", "PC61")] = NS(MediaContentArray=None)
    await _client(svc).get_media(["PC61"], media_type="Document")
    _, kwargs = svc.calls[-1]
    assert kwargs["mediaType"] == "Document"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test_promostandards_client.py -v -k "media"
```

Expected: FAIL — `test_get_media_uses_v110_and_sends_mediatype_image` reports `wsVersion == "1.0.0"` and missing `mediaType` key.

- [ ] **Step 3: Patch `get_media` and `_sync_get_media`**

Replace the existing `get_media` and `_sync_get_media` methods (around lines 382–399) with:

```python
    async def get_media(
        self,
        product_ids: list[str],
        ws_version: str = "1.1.0",
        media_type: str = "Image",
    ) -> list[PSMediaItem]:
        return await asyncio.to_thread(
            self._sync_get_media, product_ids, ws_version, media_type
        )

    def _sync_get_media(
        self, product_ids: list[str], ws_version: str, media_type: str
    ) -> list[PSMediaItem]:
        svc = self._get_service()
        out: list[PSMediaItem] = []
        for pid in product_ids:
            try:
                response = svc.getMediaContent(
                    productId=pid,
                    mediaType=media_type,
                    **self._auth(ws_version),
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("getMediaContent(%s) failed: %s", pid, exc)
                continue
            out.extend(self._parse_media(response, pid))
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest test_promostandards_client.py -v -k "media"
```

Expected: PASS for both new tests plus any pre-existing `test_media_*` tests.

- [ ] **Step 5: Commit**

```bash
cd /Users/tanishq/Documents/project-files/api-hub/api-hub
git add backend/modules/promostandards/client.py backend/test_promostandards_client.py
git commit -m "fix(promostandards): default Media Content to v1.1.0 with required mediaType"
```

---

## Task 4: Inventory — nested `Quantity/value` parsing, per-warehouse aggregation, cap removal

SanMar returns `<quantityAvailable><Quantity><uom>EA</uom><value>1045</value></Quantity></quantityAvailable>`. The current parser calls `_coerce_int()` on the whole object and gets `0`. Each `<InventoryLocation>` also carries its own `<inventoryLocationQuantity><Quantity><value>N</value></Quantity></inventoryLocationQuantity>`. Aggregate across locations, pick the highest-stock warehouse as primary. Remove the 500-item cap — SanMar reports up to 3000 per warehouse and 8 warehouses per part.

**Files:**
- Modify: `backend/modules/promostandards/client.py`
- Modify: `backend/test_promostandards_client.py`

- [ ] **Step 1: Update the existing cap test**

Open `backend/test_promostandards_client.py` and locate `test_inventory_cap_and_shape`. Replace the assertion block (the last four `assert` lines) with:

```python
    assert by_part["PC61-NVY-M"].quantity_available == 350
    assert by_part["PC61-NVY-M"].warehouse_code == "Seattle"
    # Cap removed — SanMar reports up to 3000 per warehouse × 8 warehouses.
    assert by_part["PC61-NVY-L"].quantity_available == 99999
    assert by_part["PC61-NVY-L"].warehouse_code is None
```

Also rename the function for clarity:

```python
async def test_inventory_flat_quantity_still_parses():
```

(Replace the existing `test_inventory_cap_and_shape` line with the above.)

- [ ] **Step 2: Add the new SanMar-shape tests**

Append to `backend/test_promostandards_client.py`:

```python
async def test_inventory_reads_nested_quantity_value():
    """SanMar wraps inventory qty as <quantityAvailable><Quantity><value>N</value></Quantity></quantityAvailable>."""
    svc = FakeService()
    svc.responses[("getInventoryLevels", "K420")] = NS(
        Inventory=NS(
            productId="K420",
            PartInventoryArray=NS(
                PartInventory=[
                    NS(
                        partId="92032",
                        quantityAvailable=NS(Quantity=NS(uom="EA", value="1045")),
                        InventoryLocationArray=None,
                    )
                ]
            ),
        )
    )
    levels = await _client(svc).get_inventory(["K420"])
    assert len(levels) == 1
    assert levels[0].part_id == "92032"
    assert levels[0].quantity_available == 1045


async def test_inventory_aggregates_per_warehouse_and_picks_primary():
    """Sum per-warehouse quantities; warehouse_code = highest-stock location."""
    svc = FakeService()
    svc.responses[("getInventoryLevels", "K420")] = NS(
        Inventory=NS(
            productId="K420",
            PartInventoryArray=NS(
                PartInventory=[
                    NS(
                        partId="92032",
                        # Top-level qty omitted: must aggregate from locations.
                        quantityAvailable=None,
                        InventoryLocationArray=NS(
                            InventoryLocation=[
                                NS(
                                    inventoryLocationId="1",
                                    inventoryLocationName="Seattle",
                                    inventoryLocationQuantity=NS(
                                        Quantity=NS(value="200")
                                    ),
                                ),
                                NS(
                                    inventoryLocationId="3",
                                    inventoryLocationName="Dallas",
                                    inventoryLocationQuantity=NS(
                                        Quantity=NS(value="500")
                                    ),
                                ),
                                NS(
                                    inventoryLocationId="4",
                                    inventoryLocationName="Reno",
                                    inventoryLocationQuantity=NS(
                                        Quantity=NS(value="161")
                                    ),
                                ),
                            ]
                        ),
                    )
                ]
            ),
        )
    )
    levels = await _client(svc).get_inventory(["K420"])
    assert len(levels) == 1
    assert levels[0].quantity_available == 861  # 200 + 500 + 161
    assert levels[0].warehouse_code == "Dallas"  # highest-stock


async def test_inventory_prefers_top_level_when_locations_empty():
    """If top-level qty is set and no per-location qty, use top-level."""
    svc = FakeService()
    svc.responses[("getInventoryLevels", "PC61")] = NS(
        Inventory=NS(
            productId="PC61",
            PartInventoryArray=NS(
                PartInventory=[
                    NS(
                        partId="PC61-M",
                        quantityAvailable=NS(Quantity=NS(value="42")),
                        InventoryLocationArray=None,
                    )
                ]
            ),
        )
    )
    levels = await _client(svc).get_inventory(["PC61"])
    assert levels[0].quantity_available == 42
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest test_promostandards_client.py -v -k "inventory"
```

Expected: the original `test_inventory_flat_quantity_still_parses` passes the first two asserts but fails on `99999` (current cap truncates to 500). The three new tests also fail — nested Quantity path and aggregation logic are absent.

- [ ] **Step 4: Remove the inventory cap constant**

In `backend/modules/promostandards/client.py`, delete the constant definition (around lines 38–41) and its usage. Replace:

```python
# PromoStandards caps inventory at 500 per the spec — anything larger is
# reported as exactly 500. Mirror that here so downstream callers don't have
# to special-case it.
_INVENTORY_CAP = 500
```

with:

```python
# PromoStandards does not mandate a cap; SanMar reports up to 3000 per
# warehouse × 8 warehouses. Leave raw values through to callers.
```

- [ ] **Step 5: Patch `_parse_inventory`**

Replace the `_parse_inventory` method (around lines 280–312) with:

```python
    def _parse_inventory(self, response: Any, product_id: str) -> Iterable[PSInventoryLevel]:
        inv_root = _attr(response, "Inventory", "inventory") or response
        for inv_record in _as_list(inv_root):
            rec_pid = _text(_attr(inv_record, "productId")) or product_id
            parts_container = _attr(
                inv_record, "PartInventoryArray", "partInventoryArray"
            )
            part_items = _as_list(_attr(parts_container, "PartInventory", "partInventory"))
            for part in part_items:
                part_id = _text(_attr(part, "partId", "part_id"))
                if not part_id:
                    continue
                qty, warehouse = self._extract_inventory_qty_and_warehouse(part)
                yield PSInventoryLevel(
                    product_id=rec_pid,
                    part_id=part_id,
                    quantity_available=qty,
                    warehouse_code=warehouse,
                )

    def _extract_inventory_qty_and_warehouse(self, part: Any) -> tuple[int, str | None]:
        """Return (total_quantity, primary_warehouse_name) for one part.

        SanMar nests qty in ``<quantityAvailable><Quantity><value>N</value></Quantity></quantityAvailable>``
        and repeats ``<InventoryLocation>`` with its own ``<inventoryLocationQuantity>``.
        Aggregate across locations when present; otherwise fall back to the
        top-level ``quantityAvailable`` value. Primary warehouse is the
        highest-stock location.
        """
        # 1. Enumerate per-location quantities.
        loc_container = _attr(part, "InventoryLocationArray", "inventoryLocationArray")
        locs = _as_list(_attr(loc_container, "InventoryLocation", "inventoryLocation"))
        best_qty = -1
        best_name: str | None = None
        sum_qty = 0
        any_location_qty = False
        for loc in locs:
            loc_qty_wrapper = _attr(loc, "inventoryLocationQuantity")
            quantity_obj = _attr(loc_qty_wrapper, "Quantity") if loc_qty_wrapper else None
            loc_qty_raw = _attr(quantity_obj, "value") if quantity_obj else None
            if loc_qty_raw is None:
                continue
            any_location_qty = True
            loc_qty = self._coerce_int(loc_qty_raw)
            sum_qty += loc_qty
            if loc_qty > best_qty:
                best_qty = loc_qty
                best_name = _text(
                    _attr(loc, "inventoryLocationName", "inventoryLocationId", "name")
                )

        if any_location_qty:
            return sum_qty, best_name

        # 2. No per-location quantities — use top-level quantityAvailable.
        qty_container = _attr(part, "quantityAvailable", "quantity")
        # SanMar shape: nested Quantity/value
        nested_q = _attr(qty_container, "Quantity") if qty_container is not None else None
        if nested_q is not None:
            qty = self._coerce_int(_attr(nested_q, "value"))
        else:
            # Flat-int shape (existing non-SanMar suppliers).
            qty = self._coerce_int(qty_container)

        # Warehouse name from first location entry, if any.
        warehouse_name: str | None = None
        if locs:
            warehouse_name = _text(
                _attr(locs[0], "inventoryLocationName", "inventoryLocationId", "name")
            )
        return qty, warehouse_name
```

- [ ] **Step 6: Run the inventory tests**

```bash
pytest test_promostandards_client.py -v -k "inventory"
```

Expected: all four inventory tests PASS (one flat, one nested, one aggregated, one top-level-only).

- [ ] **Step 7: Run the full client test suite**

```bash
pytest test_promostandards_client.py -v
```

Expected: every test PASSes. If a normalizer test references the old cap, update the expected value inline before committing.

- [ ] **Step 8: Commit**

```bash
cd /Users/tanishq/Documents/project-files/api-hub/api-hub
git add backend/modules/promostandards/client.py backend/test_promostandards_client.py
git commit -m "fix(promostandards): parse SanMar nested inventory Quantity/value and aggregate per-warehouse"
```

---

## Task 5: Pricing and Configuration — required SanMar params

SanMar's PPC WSDL requires `currency`, `fobId`, `priceType`, `localizationCountry`, `localizationLanguage`, and `configurationType`. The current client sends only `productId` + `_auth`. Without these, SanMar returns a SOAP fault.

**Files:**
- Modify: `backend/modules/promostandards/client.py`
- Modify: `backend/test_promostandards_client.py`

- [ ] **Step 1: Write the failing tests**

Append to `backend/test_promostandards_client.py`:

```python
async def test_get_pricing_sends_required_sanmar_params():
    """SanMar PPC requires currency/fobId/priceType/localization/configurationType."""
    svc = FakeService()
    svc.responses[("getConfigurationAndPricing", "K500")] = NS(
        Configuration=NS(PartArray=None)
    )
    await _client(svc).get_pricing(["K500"])
    _, kwargs = svc.calls[-1]
    assert kwargs["currency"] == "USD"
    assert kwargs["fobId"] == "1"
    assert kwargs["priceType"] == "Net"
    assert kwargs["localizationCountry"] == "US"
    assert kwargs["localizationLanguage"] == "EN"
    assert kwargs["configurationType"] == "Blank"


async def test_get_pricing_accepts_explicit_overrides():
    svc = FakeService()
    svc.responses[("getConfigurationAndPricing", "K500")] = NS(
        Configuration=NS(PartArray=None)
    )
    await _client(svc).get_pricing(
        ["K500"],
        currency="CAD",
        fob_id="6",
        price_type="List",
        localization_country="CA",
        localization_language="FR",
        configuration_type="Configured",
    )
    _, kwargs = svc.calls[-1]
    assert kwargs["currency"] == "CAD"
    assert kwargs["fobId"] == "6"
    assert kwargs["priceType"] == "List"
    assert kwargs["localizationCountry"] == "CA"
    assert kwargs["localizationLanguage"] == "FR"
    assert kwargs["configurationType"] == "Configured"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest test_promostandards_client.py -v -k "get_pricing_sends or get_pricing_accepts"
```

Expected: FAIL — `KeyError: 'currency'` because current `getConfigurationAndPricing` call doesn't pass these params.

- [ ] **Step 3: Patch `get_pricing` and `_sync_get_pricing`**

Replace the existing `get_pricing` and `_sync_get_pricing` methods (around lines 328–347) with:

```python
    async def get_pricing(
        self,
        product_ids: list[str],
        ws_version: str = "1.0.0",
        currency: str = "USD",
        fob_id: str = "1",
        price_type: str = "Net",
        localization_country: str = "US",
        localization_language: str = "EN",
        configuration_type: str = "Blank",
    ) -> list[PSPricePoint]:
        return await asyncio.to_thread(
            self._sync_get_pricing,
            product_ids,
            ws_version,
            currency,
            fob_id,
            price_type,
            localization_country,
            localization_language,
            configuration_type,
        )

    def _sync_get_pricing(
        self,
        product_ids: list[str],
        ws_version: str,
        currency: str,
        fob_id: str,
        price_type: str,
        localization_country: str,
        localization_language: str,
        configuration_type: str,
    ) -> list[PSPricePoint]:
        svc = self._get_service()
        out: list[PSPricePoint] = []
        for pid in product_ids:
            try:
                response = svc.getConfigurationAndPricing(
                    productId=pid,
                    currency=currency,
                    fobId=fob_id,
                    priceType=price_type,
                    localizationCountry=localization_country,
                    localizationLanguage=localization_language,
                    configurationType=configuration_type,
                    **self._auth(ws_version),
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("getConfigurationAndPricing(%s) failed: %s", pid, exc)
                continue
            out.extend(self._parse_pricing(response, pid))
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest test_promostandards_client.py -v -k "pricing"
```

Expected: all pricing tests PASS, including the two new and the pre-existing `test_pricing_parses_tiers` + `test_pricing_skips_bad_rows`.

- [ ] **Step 5: Run the full client suite and regression tests**

```bash
pytest test_promostandards_client.py -v
pytest tests/test_promostandards_normalizer.py -v
```

Expected: both suites PASS. If the normalizer test mocks `get_pricing`, the new kwargs don't affect it.

- [ ] **Step 6: Commit**

```bash
cd /Users/tanishq/Documents/project-files/api-hub/api-hub
git add backend/modules/promostandards/client.py backend/test_promostandards_client.py
git commit -m "fix(promostandards): pass SanMar-required params to getConfigurationAndPricing"
```

---

## Task 6: Smoke test script

Standalone CLI under `backend/scripts/sanmar_smoke.py`. Loads the SanMar supplier row from Postgres (so creds stay encrypted via `EncryptedJSON`), instantiates four `PromoStandardsClient` instances against hardcoded SanMar prod WSDLs, runs getProduct / getInventoryLevels / getMediaContent / getConfigurationAndPricing for a default SKU list (`PC61`, `K420`, `LPC61`, `MM1000`), and prints one summary line per call. Exits non-zero on any failure.

**Files:**
- Create: `backend/scripts/__init__.py`
- Create: `backend/scripts/sanmar_smoke.py`
- Create: `backend/tests/test_sanmar_smoke.py`

- [ ] **Step 1: Create the package marker**

```bash
mkdir -p /Users/tanishq/Documents/project-files/api-hub/api-hub/backend/scripts
touch /Users/tanishq/Documents/project-files/api-hub/api-hub/backend/scripts/__init__.py
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_sanmar_smoke.py`:

```python
"""Smoke-script unit test — mocks the four PromoStandardsClient calls and
verifies the runner prints a summary line per service and exits zero on
all-success, one on any failure.
"""
from __future__ import annotations

from types import SimpleNamespace as NS
from unittest.mock import AsyncMock

import pytest

from modules.promostandards.schemas import (
    PSInventoryLevel,
    PSMediaItem,
    PSPricePoint,
    PSProductData,
    PSProductPart,
)
from scripts import sanmar_smoke


@pytest.fixture
def happy_path(monkeypatch):
    def fake_client_factory(wsdl: str, auth: dict):
        stub = NS()
        stub.get_product = AsyncMock(
            return_value=PSProductData(
                product_id="PC61",
                product_name="Essential Tee",
                brand="Port & Company",
                categories=["T-Shirts"],
                parts=[PSProductPart(part_id="PC61-NVY-M", color_name="Navy", size_name="M")],
            )
        )
        stub.get_inventory = AsyncMock(
            return_value=[PSInventoryLevel(
                product_id="PC61", part_id="PC61-NVY-M",
                quantity_available=120, warehouse_code="Seattle",
            )]
        )
        stub.get_media = AsyncMock(
            return_value=[PSMediaItem(
                product_id="PC61", url="https://cdnm.sanmar.com/catalog/images/PC61.jpg",
                media_type="Front",
            )]
        )
        stub.get_pricing = AsyncMock(
            return_value=[PSPricePoint(
                product_id="PC61", part_id="PC61-NVY-M", price=3.99, quantity_min=1,
            )]
        )
        return stub

    monkeypatch.setattr(sanmar_smoke, "PromoStandardsClient", fake_client_factory)

    async def fake_load_auth():
        return {"id": "user", "password": "pass"}

    monkeypatch.setattr(sanmar_smoke, "load_sanmar_auth", fake_load_auth)


async def test_smoke_prints_all_four_services_per_sku(happy_path, capsys):
    code = await sanmar_smoke.run_smoke(["PC61"], sanmar_smoke.PROD_WSDLS)
    out = capsys.readouterr().out
    assert code == 0
    assert "[PRODUCT]" in out
    assert "[INVENTORY]" in out
    assert "[MEDIA]" in out
    assert "[PRICING]" in out
    assert "PC61" in out
    assert "4/4 calls passed" in out


async def test_smoke_returns_nonzero_when_auth_missing(monkeypatch, capsys):
    async def empty_auth():
        return {}
    monkeypatch.setattr(sanmar_smoke, "load_sanmar_auth", empty_auth)
    code = await sanmar_smoke.run_smoke(["PC61"], sanmar_smoke.PROD_WSDLS)
    assert code == 1


async def test_smoke_counts_failures(monkeypatch, capsys):
    def client_with_one_failing_service(wsdl: str, auth: dict):
        stub = NS()
        stub.get_product = AsyncMock(return_value=None)  # counts as failure
        stub.get_inventory = AsyncMock(return_value=[])
        stub.get_media = AsyncMock(return_value=[])
        stub.get_pricing = AsyncMock(return_value=[])
        return stub

    monkeypatch.setattr(sanmar_smoke, "PromoStandardsClient", client_with_one_failing_service)

    async def fake_auth():
        return {"id": "u", "password": "p"}
    monkeypatch.setattr(sanmar_smoke, "load_sanmar_auth", fake_auth)

    code = await sanmar_smoke.run_smoke(["PC61"], sanmar_smoke.PROD_WSDLS)
    out = capsys.readouterr().out
    assert code == 1
    assert "3/4 calls passed" in out
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd api-hub/backend && source .venv/bin/activate
pytest tests/test_sanmar_smoke.py -v
```

Expected: `ModuleNotFoundError: No module named 'scripts.sanmar_smoke'`.

- [ ] **Step 4: Create `backend/scripts/sanmar_smoke.py`**

```python
#!/usr/bin/env python3
"""SanMar PromoStandards smoke test.

Runs getProduct / getInventoryLevels / getMediaContent / getConfigurationAndPricing
against SanMar endpoints for a curated SKU list and prints one summary line
per service call. Exits non-zero on any failure.

Usage:
    cd api-hub/backend && source .venv/bin/activate
    python scripts/sanmar_smoke.py                      # prod + default SKUs
    python scripts/sanmar_smoke.py --test               # test-ws.sanmar.com
    python scripts/sanmar_smoke.py --sku PC61 --sku K420

Prerequisite: a Supplier row with slug='sanmar' must exist in the DB with
auth_config={"id": "<SanMar.com username>", "password": "<SanMar.com password>"}.
See docs/sanmar_smoke_runbook.md for the one-time setup steps.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Allow running from backend/ root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from database import async_session  # noqa: E402
from modules.promostandards.client import PromoStandardsClient  # noqa: E402
from modules.suppliers.models import Supplier  # noqa: E402

log = logging.getLogger("sanmar_smoke")


PROD_WSDLS = {
    "product": "https://ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl",
    "inventory": "https://ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL",
    "media": "https://ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl",
    "pricing": "https://ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL",
}

TEST_WSDLS = {
    "product": "https://test-ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl",
    "inventory": "https://test-ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL",
    "media": "https://test-ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl",
    "pricing": "https://test-ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL",
}

DEFAULT_SKUS = ["PC61", "K420", "LPC61", "MM1000"]


async def load_sanmar_auth() -> dict:
    """Fetch SanMar Supplier row and return its decrypted auth_config dict."""
    async with async_session() as db:
        supplier = (
            await db.execute(select(Supplier).where(Supplier.slug == "sanmar"))
        ).scalar_one_or_none()
    if supplier is None:
        raise RuntimeError(
            "Supplier slug='sanmar' not found. Create one via /suppliers UI first."
        )
    return dict(supplier.auth_config or {})


async def run_smoke(skus: list[str], wsdls: dict[str, str]) -> int:
    auth = await load_sanmar_auth()
    if not auth.get("id") or not auth.get("password"):
        print("[ERROR] auth_config missing id/password. Set via /suppliers UI.")
        return 1

    pd_client = PromoStandardsClient(wsdls["product"], auth)
    inv_client = PromoStandardsClient(wsdls["inventory"], auth)
    media_client = PromoStandardsClient(wsdls["media"], auth)
    ppc_client = PromoStandardsClient(wsdls["pricing"], auth)

    total = len(skus) * 4
    failures = 0

    for sku in skus:
        print(f"\n=== {sku} ===")

        try:
            product = await pd_client.get_product(sku)
            if product is None:
                print("  [PRODUCT] empty / fault")
                failures += 1
            else:
                print(
                    f"  [PRODUCT] name={product.product_name!r} brand={product.brand!r} "
                    f"parts={len(product.parts)} cats={product.categories[:3]}"
                )
        except Exception as exc:  # noqa: BLE001
            print(f"  [PRODUCT] FAIL: {exc}")
            failures += 1

        try:
            inv = await inv_client.get_inventory([sku])
            if not inv:
                print("  [INVENTORY] no records")
                failures += 1
            else:
                print(f"  [INVENTORY] {len(inv)} part-level records")
                for lvl in inv[:3]:
                    print(
                        f"    part={lvl.part_id} qty={lvl.quantity_available} "
                        f"primary_wh={lvl.warehouse_code!r}"
                    )
        except Exception as exc:  # noqa: BLE001
            print(f"  [INVENTORY] FAIL: {exc}")
            failures += 1

        try:
            media = await media_client.get_media([sku], media_type="Image")
            if not media:
                print("  [MEDIA] no urls")
                failures += 1
            else:
                print(f"  [MEDIA] {len(media)} urls")
                for m in media[:3]:
                    print(f"    {m.media_type}: {m.url}")
        except Exception as exc:  # noqa: BLE001
            print(f"  [MEDIA] FAIL: {exc}")
            failures += 1

        try:
            prices = await ppc_client.get_pricing([sku])
            if not prices:
                print("  [PRICING] no price points")
                failures += 1
            else:
                print(f"  [PRICING] {len(prices)} price points")
                for p in prices[:3]:
                    print(
                        f"    part={p.part_id} price={p.price} min_qty={p.quantity_min}"
                    )
        except Exception as exc:  # noqa: BLE001
            print(f"  [PRICING] FAIL: {exc}")
            failures += 1

    print(f"\n=== Summary: {total - failures}/{total} calls passed ===")
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="SanMar PromoStandards smoke test")
    parser.add_argument(
        "--test",
        action="store_true",
        help="Use test-ws.sanmar.com endpoints instead of production",
    )
    parser.add_argument(
        "--sku",
        action="append",
        dest="skus",
        help="SKU to test (repeatable). Default list: PC61, K420, LPC61, MM1000.",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    skus = args.skus or DEFAULT_SKUS
    wsdls = TEST_WSDLS if args.test else PROD_WSDLS
    return asyncio.run(run_smoke(skus, wsdls))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Run the script test**

```bash
cd api-hub/backend && source .venv/bin/activate
pytest tests/test_sanmar_smoke.py -v
```

Expected: all three tests PASS.

- [ ] **Step 6: Verify the script imports cleanly**

```bash
python -c "from scripts import sanmar_smoke; print(sanmar_smoke.DEFAULT_SKUS)"
```

Expected: `['PC61', 'K420', 'LPC61', 'MM1000']`.

- [ ] **Step 7: Verify `--help` renders**

```bash
python scripts/sanmar_smoke.py --help
```

Expected: argparse help text listing `--test`, `--sku`, `-v`. Exit code 0.

- [ ] **Step 8: Commit**

```bash
cd /Users/tanishq/Documents/project-files/api-hub/api-hub
git add backend/scripts/__init__.py backend/scripts/sanmar_smoke.py backend/tests/test_sanmar_smoke.py
git commit -m "feat(sanmar): add PromoStandards smoke-test CLI script"
```

---

## Task 7: Runbook for supplier row setup + manual smoke execution

Doc-only. Captures the one-time steps an operator runs to create the SanMar Supplier row, patch the `endpoint_cache`, and execute the smoke script with real production credentials.

**Files:**
- Create: `docs/sanmar_smoke_runbook.md`

- [ ] **Step 1: Create the runbook**

Create `docs/sanmar_smoke_runbook.md`:

```markdown
# SanMar PromoStandards Smoke Test — Runbook

One-time manual steps to validate the `PromoStandardsClient` against SanMar
production SOAP endpoints using real credentials supplied by SanMar Integration
Support.

## Prerequisites

- PostgreSQL running: `docker compose up -d postgres`
- Backend deps installed: `cd backend && source .venv/bin/activate && pip install -r requirements.txt`
- Client patches landed (Tasks 1–5 of the smoke-test plan)
- SanMar credentials in hand: SanMar Customer Number, SanMar.com username, SanMar.com password

## Step 1 — Create the SanMar Supplier row via UI

1. Start the stack:
   ```bash
   cd api-hub
   docker compose up -d postgres n8n
   cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000 &
   cd ../frontend && npm run dev &
   ```
2. Open `http://localhost:3000/suppliers` in a browser.
3. Click **Add supplier** and fill in:
   - **Name:** `SanMar`
   - **Slug:** `sanmar`
   - **Protocol:** `promostandards`
   - **PromoStandards code:** `SANM`
   - **Auth config (JSON):**
     ```json
     {"id": "<SanMar.com username>", "password": "<SanMar.com password>"}
     ```
   - **Is active:** yes
4. Save. The backend encrypts `auth_config` via the `EncryptedJSON` column type.

## Step 2 — Seed the endpoint cache

The PS directory lookup may not match SanMar's `ServiceType` strings until
verified. Seed the cache manually using a one-off SQL update. Find the
supplier UUID:

```bash
psql -h localhost -U vg_user -d vg_hub -c "SELECT id FROM suppliers WHERE slug='sanmar';"
```

Copy the UUID, then run:

```bash
psql -h localhost -U vg_user -d vg_hub <<SQL
UPDATE suppliers
SET endpoint_cache = '[
  {"ServiceType": "Product Data", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/ProductDataServiceV2.xml?wsdl"},
  {"ServiceType": "Inventory Levels", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/InventoryServiceBindingV2final?WSDL"},
  {"ServiceType": "Media Content", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/MediaContentServiceBinding?wsdl"},
  {"ServiceType": "Product Pricing and Configuration", "ProductionURL": "https://ws.sanmar.com:8080/promostandards/PricingAndConfigurationServiceBinding?WSDL"}
]'::jsonb
WHERE slug='sanmar';
SQL
```

## Step 3 — Run the smoke script

```bash
cd api-hub/backend && source .venv/bin/activate
python scripts/sanmar_smoke.py
```

Expected output (real values will differ):

```
=== PC61 ===
  [PRODUCT] name='Essential Tee' brand='Port & Company' parts=300+ cats=['T-Shirts']
  [INVENTORY] 300+ part-level records
    part=PC61-NVY-M qty=12345 primary_wh='Dallas'
    ...
  [MEDIA] 15+ urls
    Primary: https://cdnm.sanmar.com/catalog/images/PC61.jpg
    Front: https://cdnl.sanmar.com/imglib/mresjpg/...
    ...
  [PRICING] 300+ price points
    part=PC61-NVY-M price=3.99 min_qty=1
    ...

=== K420 ===
  ...

=== Summary: 16/16 calls passed ===
```

Exit code `0` means all calls landed. Anything non-zero means at least one
service returned a SOAP fault, empty response, or parse error — check the
corresponding `FAIL:` line in the output.

## Step 4 — Test environment variant

To hit `test-ws.sanmar.com` instead of production (optional; test env may be
offline during SanMar internal maintenance):

```bash
python scripts/sanmar_smoke.py --test
```

## Step 5 — Override SKU list

```bash
python scripts/sanmar_smoke.py --sku PC61 --sku K420
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `[ERROR] auth_config missing id/password` | Supplier row exists but creds blank | Re-save creds via `/suppliers` UI |
| `[PRODUCT] FAIL: ... authenticating failed` | Wrong username/password | Verify credentials with SanMar; confirm SanMar.com account (not FTP) |
| `[INVENTORY] FAIL: Connection refused` | WSDL unreachable | Check network; confirm port 8080 isn't firewalled |
| `[PRICING] FAIL: ... fobId required` | Client patches missing | Verify Tasks 1–5 landed: `git log --oneline backend/modules/promostandards/client.py` |
| `[MEDIA] 0 urls` but product exists | Wrong `mediaType` or account flag | Try `media_type="Document"`; contact SanMar integrations |

## Next Steps

Once all four SKUs report `4/4 calls passed`, the client is SanMar-ready. Next
plan: wire the SanMar supplier into the existing `POST /api/sync/{id}/products`
route path for a real catalog pull, then run a bounded sync against ~50 SKUs
before opening the gate to the full catalog.
```

- [ ] **Step 2: Commit**

```bash
cd /Users/tanishq/Documents/project-files/api-hub/api-hub
git add docs/sanmar_smoke_runbook.md
git commit -m "docs: add SanMar PromoStandards smoke-test runbook"
```

---

## Verification (end-to-end)

After every task is complete:

- [ ] **Run the full backend test suite**

```bash
cd api-hub/backend && source .venv/bin/activate
pytest -v
```

Expected: every pre-existing test plus every new test from Tasks 1–6 PASSes. No new warnings or errors.

- [ ] **Confirm import chain**

```bash
python -c "from scripts.sanmar_smoke import run_smoke, PROD_WSDLS, TEST_WSDLS, DEFAULT_SKUS; print(len(PROD_WSDLS))"
```

Expected: `4`.

- [ ] **Dry-run the script without real creds**

```bash
python scripts/sanmar_smoke.py
```

Expected: exits `1` with `RuntimeError: Supplier slug='sanmar' not found` or `[ERROR] auth_config missing id/password` depending on DB state. Proves the script's failure path works before real creds arrive.

Once real creds are seeded (Step 1 of the runbook), the same command must produce `Summary: 16/16 calls passed`.

---

## Out of scope for this plan

Listed here so reviewers can confirm these items do NOT need to land with the smoke test:

- Full catalog sync via `POST /api/sync/{id}/products` — deferred to a follow-up plan after smoke passes
- SFTP bulk ingestion — separate plan `docs/superpowers/specs/2026-04-22-sanmar-sftp-integration-design.md`
- SanMar proprietary services (Standard Product Info, SanMar Inventory, SanMar Pricing, Invoicing, License Plate) — PromoStandards only for this plan
- Invoice / Order Status / Shipment Notification PromoStandards services
- Frontend supplier-add UX refinements — use existing `/suppliers` page as-is
- Per-warehouse inventory breakdown in `PSInventoryLevel` / DB schema — aggregated into a single level per part for this plan; multi-warehouse expansion is a separate schema migration
- Rate-limit pacing — if the script triggers SanMar rate limiting during smoke runs, add `asyncio.sleep(0.5)` between service calls as a fast fix in a follow-up commit
