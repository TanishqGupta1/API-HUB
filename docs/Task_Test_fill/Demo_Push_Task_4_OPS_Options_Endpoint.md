# Task 4 (Demo Push Pipeline) — `GET /ops-options` Endpoint — Detail Guide

**Status:** ✅ Completed on 2026-04-27
**Branch:** `Vidhi`
**Sprint spec:** `plans/tasks/vidhi-tasks.md` (Demo Push Pipeline)
**Plan reference:** `docs/superpowers/plans/2026-04-23-demo-push-pipeline.md` → Task 4
**What you can say in one sentence:** *"I built the API endpoint that converts our hub's master-option product config into the product-scoped shape OPS expects on push, stripping the global master IDs from the body and keeping them only as traceability fields."*

---

## 1. What Got Built

| File | What Changed |
|---|---|
| `backend/modules/markup/schemas.py` | Added `OPSProductOptionSchema` + `OPSProductAttributeSchema` (24 lines added) |
| `backend/modules/markup/routes.py` | Added `GET /api/push/{customer_id}/product/{product_id}/ops-options` (~75 lines) + new imports |
| `backend/tests/test_ops_options_endpoint.py` | New test file — 2 tests, ~140 lines |

---

## 2. Background — What Is This Task About?

### Task Type
**Backend endpoint + Pydantic schemas + integration tests** — Python, FastAPI, SQLAlchemy async. No frontend.

### The Architectural Rule (From Christian's Meeting)

> **Outbound to a customer's OPS storefront uses *product options*, never *master options*.**

The hub stores options in two layers:

- **Master options** — global definitions managed in the hub (e.g. master option `9001 = "Ink Finish"` with attribute `9991 = "Gloss"`). These have OPS-internal IDs (`ops_master_option_id`, `ops_attribute_id`) that are valid in the **OPS admin**, but **not** valid on per-product push.
- **Product options** — a per-product copy created when an admin enables a master option for a specific product. Same titles and attribute keys, but bound to one product.

When pushing to a customer's storefront, OPS expects the product-scoped shape — no master IDs on the body. This endpoint does that conversion.

### Why a Dedicated Endpoint?

The existing `/payload` and `/ops-variants` endpoints handle product metadata + price/size variants. **Options** (color, finish, add-ons) are a separate, shaped-differently concern and need their own response model — hence a new route.

---

## 3. The Endpoint Contract

```
GET /api/push/{customer_id}/product/{product_id}/ops-options
Headers: X-Ingest-Secret: <env value>
```

**Returns:** `list[OPSProductOptionSchema]`

**Each item shape:**

```json
{
  "option_key": "inkFinish",
  "title": "Ink Finish",
  "options_type": "combo",
  "attributes": [
    {
      "title": "Gloss",
      "price": 5.00,
      "sort_order": 1,
      "numeric_value": 0.0,
      "source_master_attribute_id": 9991,
      "source_attribute_key": "gloss"
    }
  ],
  "source_master_option_id": 9001
}
```

**The critical detail:**
- `master_option_id` is **NOT** in the body — only `source_master_option_id` (renamed for traceability).
- `ops_attribute_id` is **NOT** on attributes — only `source_master_attribute_id`.

This satisfies the architectural rule: an OPS push body has no master-scoped IDs; we keep them as `source_*` so push_mappings (Sinchana's tables) can record the master→product link for audit.

---

## 4. How It Works — Internal Flow

```
Endpoint called with (customer_id, product_id)
       ↓
Load ProductOption rows where product_id matches AND enabled=true
  (selectinload .attributes — single query, no N+1)
       ↓
Collect distinct master_option_ids referenced
       ↓
Join MasterOption ↔ MasterOptionAttribute and look up
  raw_json.attribute_key for each (master_option_id, ops_attribute_id) pair
       ↓
For each ProductOption:
  - filter to enabled attributes only
  - skip option entirely if no attributes are enabled
  - for each attribute: compose OPSProductAttributeSchema
    using overridden_sort if set, else sort_order
  - compose OPSProductOptionSchema, attach source_master_option_id
       ↓
Return list (empty list, NOT 404, when nothing is enabled)
```

---

## 5. Code Walkthrough — The Endpoint

```python
@push_router.get(
    "/{customer_id}/product/{product_id}/ops-options",
    response_model=list[OPSProductOptionSchema],
    dependencies=[Depends(require_ingest_secret)],
)
async def ops_product_options(
    customer_id: UUID,
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
):
```

| Decision | Why |
|---|---|
| Lives on `push_router` (`/api/push`) | It's a push-time concern, alongside `/payload` + `/ops-variants` |
| `response_model=list[...]` | FastAPI auto-validates the response, generates OpenAPI docs |
| `Depends(require_ingest_secret)` | Reuses the same `X-Ingest-Secret` header n8n already sends — no new auth |
| `selectinload(ProductOption.attributes)` | Eager-load attributes in one extra query — avoids N+1 when iterating |
| `if not enabled_attrs: continue` | An option with no enabled attributes is meaningless — skip it entirely |
| Empty list (not 404) when nothing matches | Matches HTTP semantics: "the resource is empty" ≠ "the resource does not exist" |

### The Master Lookup

`ProductOption.master_option_id` stores an **integer** — the OPS master option ID (not a UUID FK to `master_options.id`). To find the matching `MasterOption` row + attribute keys we join through it:

```python
mo_ids = {po.master_option_id for po in po_rows if po.master_option_id is not None}
moas = await db.execute(
    select(MasterOption, MasterOptionAttribute)
    .join(MasterOptionAttribute, MasterOption.id == MasterOptionAttribute.master_option_id)
    .where(MasterOption.ops_master_option_id.in_(mo_ids))
)
for mo, ma in moas.all():
    raw = ma.raw_json or {}
    attr_key = raw.get("attribute_key") if isinstance(raw, dict) else None
    moa_map[(mo.ops_master_option_id, ma.ops_attribute_id)] = attr_key
```

`source_attribute_key` reads from `MasterOptionAttribute.raw_json["attribute_key"]` — the supplier's stable string identifier (e.g. `"gloss"`). Useful downstream for matching attributes across pushes.

---

## 6. The Schemas

```python
class OPSProductAttributeSchema(BaseModel):
    title: str
    price: float = 0.0
    sort_order: int = 0
    numeric_value: float = 0.0
    source_master_attribute_id: Optional[int] = None
    source_attribute_key: Optional[str] = None


class OPSProductOptionSchema(BaseModel):
    option_key: str
    title: str
    options_type: Optional[str] = None
    attributes: list[OPSProductAttributeSchema] = Field(default_factory=list)
    source_master_option_id: Optional[int] = None
```

The naming is the contract:
- **No** `master_option_id` field
- **No** `ops_attribute_id` field
- The `source_*` prefix communicates "this is for traceability, not for OPS push"

---

## 7. Tests

`backend/tests/test_ops_options_endpoint.py` — 2 async tests using httpx + ASGITransport.

| Test | What It Asserts |
|---|---|
| `test_ops_options_returns_product_scoped_shape` | After ingesting a master option + enabling it on a product with a price override, the endpoint returns the product-scoped shape. Specifically asserts `master_option_id` is **not** in the response body and `source_master_option_id == 9001`. |
| `test_ops_options_empty_when_nothing_enabled` | A product with no enabled options returns 200 + `[]`, not 404. |

Test cleanup uses an autouse fixture that deletes `Customer.name LIKE "OPO-%"` rows + `MasterOption.ops_master_option_id >= 9000` rows so reruns don't leave residue. Suppliers/products cascade away via `conftest.py`'s `_cleanup_test_suppliers` (which keys on `slug='vg-ops-test'`).

### Running the Tests

```bash
docker compose restart api && sleep 4
docker compose exec -T api pytest tests/test_ops_options_endpoint.py -v
```

Expected: **2 PASS**.

---

## 8. Edge Cases Handled

| Scenario | Behavior |
|---|---|
| Product has zero enabled options | Returns `[]` (HTTP 200) |
| Option enabled but no attribute enabled | Option skipped entirely (not returned with empty `attributes`) |
| Attribute has `overridden_sort` set | Uses overridden value instead of `sort_order` |
| `master_option_id` is null on a ProductOption | Lookup is skipped for that option, `source_master_option_id` ends up `None` |
| `MasterOptionAttribute.raw_json` is malformed (not a dict) | Defaults `attr_key` to `None` instead of raising |
| Wrong / missing `X-Ingest-Secret` header | 401 from `require_ingest_secret` dep — same gate as the rest of the push routes |

---

## 9. Build Verification

| Check | Result |
|---|---|
| AST syntax check on schemas.py / routes.py / test file | ✅ pass |
| New imports compile (`selectinload`, `MasterOption`, `MasterOptionAttribute`) | ✅ resolved against existing models |
| Response shape matches the architectural rule (no master IDs in core) | ✅ asserted in test |

Tests not run here — needs Postgres. Run locally per Section 7.

---

## 10. What Comes Next

| Next Task | What It Adds | Blocked? |
|---|---|---|
| **Task 5** — n8n workflow extension | Calls this endpoint and uses the response to build push_mappings | ❌ No — built next, see Demo_Push_Task_5 |
| **Sinchana Task 3** — `POST /api/push-mappings` | Receives the payload Task 5 builds | 🔴 Not done by Vidhi — owned by Sinchana |
| **OPS beta mutations ship** | `setAdditionalOption`, `setAdditionalOptionAttributes`, `setProductsAttributePrice` — replace the Stub Apply Options Code node in Task 5 | 🔴 Waiting on OPS team |
