# Product Options Ingest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **⚠ Commit policy (project rule):** User runs commits manually. Each task ends with a **"Stage"** step listing exact `git add` paths + a suggested commit message. Do NOT run `git commit` automatically. Never add `Co-Authored-By` lines.

**Goal:** Ingest VG product additional options (option groups + attribute values) from OPS GraphQL into API Hub catalog DB, expose on the PDP API response, and render on the storefront product detail page.

**Architecture:** Fix n8n node to return 4 missing fields per option, then add two normalized DB tables (`product_options`, `product_option_attributes`), extend the ingest endpoint to upsert them, add read schemas, and render on PDP. Options are upserted by `(product_id, option_key)`; attributes are delete-and-reinsert per option (attribute titles can change between syncs).

**Tech Stack:** TypeScript (n8n node), FastAPI + async SQLAlchemy 2.0 + asyncpg (backend), Pydantic v2 (schemas), pytest-asyncio (tests), Next.js 15 + Tailwind (frontend).

---

## File Structure

| File | Role |
|------|------|
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` | Add 4 fields to `productAdditionalOptionsFields` multiOptions (lines 3357–3371) |
| `backend/modules/catalog/models.py` | Add `ProductOption` + `ProductOptionAttribute` models; add `options` relationship to `Product` |
| `backend/modules/catalog/schemas.py` | Add `OptionAttributeIngest`, `OptionIngest`; extend `ProductIngest`; add `ProductOptionAttributeRead`, `ProductOptionRead`; extend `ProductRead` |
| `backend/modules/catalog/ingest.py` | Extend `ingest_products` to upsert options + delete/reinsert attributes |
| `backend/modules/catalog/routes.py` | Add `selectinload(Product.options).selectinload(ProductOption.attributes)` to `get_product` |
| `backend/tests/test_catalog_ingest.py` | Add 2 tests: creates options, idempotent update |
| `frontend/src/lib/types.ts` | Add `ProductOption`, `ProductOptionAttribute`; extend `Product` |
| `frontend/src/app/storefront/vg/product/[product_id]/page.tsx` | Render options section |

---

## Task 1: Fix n8n node — add missing `productAdditionalOptionsFields`

**Files:**
- Modify: `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts:3357-3371`

- [ ] **Step 1: Replace the `options` array and `default` in `productAdditionalOptionsFields`**

Current block at lines 3357–3371:
```typescript
options: [
    { name: '🔘 Select All Option Fields', value: 'SELECT_ALL' },
    { name: '🔘 Deselect All Option Fields', value: 'DESELECT_ALL' },
    { name: '─────────────────────────────', value: 'SEPARATOR' },
    { name: 'Option Key', value: 'option_key' },
    { name: 'Options Type', value: 'options_type' },
    { name: 'Required', value: 'required' },
    { name: 'Sort Order', value: 'sort_order' },
],
default: [
    'option_key',
    'options_type',
    'required',
    'sort_order',
],
```

Replace with:
```typescript
options: [
    { name: '🔘 Select All Option Fields', value: 'SELECT_ALL' },
    { name: '🔘 Deselect All Option Fields', value: 'DESELECT_ALL' },
    { name: '─────────────────────────────', value: 'SEPARATOR' },
    { name: 'Product Additional Option ID', value: 'product_additional_option_id' },
    { name: 'Master Option ID',             value: 'master_option_id' },
    { name: 'Title',                        value: 'title' },
    { name: 'Option Key',                   value: 'option_key' },
    { name: 'Options Type',                 value: 'options_type' },
    { name: 'Required',                     value: 'required' },
    { name: 'Sort Order',                   value: 'sort_order' },
    { name: 'Attributes',                   value: 'attributes' },
],
default: [
    'product_additional_option_id',
    'master_option_id',
    'title',
    'option_key',
    'options_type',
    'required',
    'sort_order',
    'attributes',
],
```

- [ ] **Step 2: Build the node to verify no TypeScript errors**

Run: `cd n8n-nodes-onprintshop && npm run build`
Expected: Build succeeds with no errors. `dist/` updated.

- [ ] **Step 3: Stage**

```bash
git add n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts
# suggested: fix(ops-node): add title, master_option_id, ops_option_id, attributes to productAdditionalOptionsFields
```

---

## Task 2: Backend models — `ProductOption` + `ProductOptionAttribute`

**Files:**
- Modify: `backend/modules/catalog/models.py`

- [ ] **Step 1: Add imports and two model classes**

Append to `backend/modules/catalog/models.py` after the `ProductImage` class (after line 95):

```python
class ProductOption(Base):
    __tablename__ = "product_options"
    __table_args__ = (
        UniqueConstraint("product_id", "option_key", name="uq_product_option_key"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE")
    )
    ops_option_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    master_option_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    option_key: Mapped[str] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(255))
    options_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    required: Mapped[bool] = mapped_column(default=False)
    status: Mapped[int] = mapped_column(Integer, default=1)

    product: Mapped["Product"] = relationship(back_populates="options")
    attributes: Mapped[list["ProductOptionAttribute"]] = relationship(
        back_populates="option", cascade="all, delete-orphan"
    )


class ProductOptionAttribute(Base):
    __tablename__ = "product_option_attributes"
    __table_args__ = (
        UniqueConstraint("product_option_id", "title", name="uq_option_attribute_title"),
    )

    id: Mapped[uuid_mod.UUID] = mapped_column(primary_key=True, default=uuid_mod.uuid4)
    product_option_id: Mapped[uuid_mod.UUID] = mapped_column(
        ForeignKey("product_options.id", ondelete="CASCADE")
    )
    ops_attribute_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(255))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[int] = mapped_column(Integer, default=1)

    option: Mapped["ProductOption"] = relationship(back_populates="attributes")
```

- [ ] **Step 2: Add `options` relationship to `Product`**

In the `Product` class (lines 51–57), add after `images` relationship:

```python
options: Mapped[list["ProductOption"]] = relationship(
    back_populates="product", cascade="all, delete-orphan"
)
```

- [ ] **Step 3: Verify tables auto-create on startup**

Run: `docker compose exec -T api sh -c "cd /app && python -c 'from modules.catalog.models import ProductOption, ProductOptionAttribute; print(\"OK\")'"` 

Expected: `OK`

Then check tables exist:
Run: `docker compose exec -T postgres psql -U vg_user -d vg_hub -c "\dt product_option*"`
Expected: Two rows — `product_option_attributes` and `product_options`.

- [ ] **Step 4: Stage**

```bash
git add backend/modules/catalog/models.py
# suggested: feat(catalog): add ProductOption + ProductOptionAttribute models
```

---

## Task 3: Backend schemas — ingest + read schemas

**Files:**
- Modify: `backend/modules/catalog/schemas.py`

- [ ] **Step 1: Add ingest schemas for options**

After `ImageIngest` (after line 91 in `schemas.py`), add:

```python
class OptionAttributeIngest(BaseModel):
    title: str
    sort_order: int = 0
    ops_attribute_id: Optional[int] = None


class OptionIngest(BaseModel):
    option_key: str
    title: str
    options_type: Optional[str] = None
    sort_order: int = 0
    master_option_id: Optional[int] = None
    ops_option_id: Optional[int] = None
    required: bool = False
    attributes: list[OptionAttributeIngest] = Field(default_factory=list)
```

- [ ] **Step 2: Extend `ProductIngest` with `options` field**

In `ProductIngest` (currently ending at line 104), add:

```python
options: list[OptionIngest] = Field(default_factory=list)
```

- [ ] **Step 3: Add read schemas**

After `ProductImageRead` (after line 28), add:

```python
class ProductOptionAttributeRead(BaseModel):
    id: UUID
    title: str
    sort_order: int
    ops_attribute_id: Optional[int] = None

    model_config = {"from_attributes": True}


class ProductOptionRead(BaseModel):
    id: UUID
    option_key: str
    title: str
    options_type: Optional[str] = None
    sort_order: int
    master_option_id: Optional[int] = None
    ops_option_id: Optional[int] = None
    required: bool
    attributes: list[ProductOptionAttributeRead] = []

    model_config = {"from_attributes": True}
```

- [ ] **Step 4: Extend `ProductRead` with `options` field**

In `ProductRead`, add after `images: list[ProductImageRead] = []`:

```python
options: list[ProductOptionRead] = []
```

- [ ] **Step 5: Verify schema import**

Run: `docker compose exec -T api sh -c "cd /app && python -c 'from modules.catalog.schemas import ProductOptionRead, OptionIngest; print(\"OK\")'"` 
Expected: `OK`

- [ ] **Step 6: Stage**

```bash
git add backend/modules/catalog/schemas.py
# suggested: feat(catalog): add option ingest + read schemas
```

---

## Task 4: Write failing tests (TDD)

**Files:**
- Modify: `backend/tests/test_catalog_ingest.py`

- [ ] **Step 1: Add import at top of test file**

Confirm `select` is already imported (it is, added in Task A2 from prior plan). If not, add:
```python
from sqlalchemy import select
```

- [ ] **Step 2: Append test — creates options + attributes**

```python
@pytest.mark.asyncio
async def test_ingest_products_creates_options(client: AsyncClient, db, seed_supplier):
    from modules.catalog.models import Product, ProductOption, ProductOptionAttribute

    payload = [{
        "supplier_sku": "OPT-TEST-1",
        "product_name": "Options Test Product",
        "options": [
            {
                "option_key": "inkFinish",
                "title": "Ink Finish",
                "options_type": "Radio Button",
                "sort_order": 0,
                "master_option_id": 112,
                "ops_option_id": 456,
                "required": False,
                "attributes": [
                    {"title": "Gloss", "sort_order": 0},
                    {"title": "Matte", "sort_order": 1},
                    {"title": "FLX+",  "sort_order": 2},
                ]
            },
            {
                "option_key": "cutting",
                "title": "Cutting",
                "options_type": "Radio Button",
                "sort_order": 1,
                "master_option_id": None,
                "required": False,
                "attributes": [
                    {"title": "Yes", "sort_order": 0},
                    {"title": "No",  "sort_order": 1},
                ]
            }
        ]
    }]
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=payload,
    )
    assert r.status_code == 200
    assert r.json()["records_processed"] == 1

    prod = (await db.execute(
        select(Product).where(Product.supplier_sku == "OPT-TEST-1")
    )).scalar_one()

    opts = (await db.execute(
        select(ProductOption).where(ProductOption.product_id == prod.id)
        .order_by(ProductOption.sort_order)
    )).scalars().all()
    assert len(opts) == 2
    assert opts[0].option_key == "inkFinish"
    assert opts[0].master_option_id == 112
    assert opts[0].ops_option_id == 456
    assert opts[1].option_key == "cutting"
    assert opts[1].master_option_id is None

    ink_attrs = (await db.execute(
        select(ProductOptionAttribute).where(ProductOptionAttribute.product_option_id == opts[0].id)
    )).scalars().all()
    assert {a.title for a in ink_attrs} == {"Gloss", "Matte", "FLX+"}
```

- [ ] **Step 3: Append test — idempotent + attribute update**

```python
@pytest.mark.asyncio
async def test_ingest_products_options_idempotent(client: AsyncClient, db, seed_supplier):
    from modules.catalog.models import Product, ProductOption, ProductOptionAttribute

    base_payload = [{
        "supplier_sku": "OPT-TEST-2",
        "product_name": "Idempotent Options",
        "options": [{
            "option_key": "lamMaterial",
            "title": "Laminate",
            "options_type": "Drop Down",
            "sort_order": 0,
            "required": False,
            "attributes": [
                {"title": "None",  "sort_order": 0},
                {"title": "Gloss", "sort_order": 1},
            ]
        }]
    }]
    await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=base_payload,
    )

    # Second ingest — attribute list changes (add "Matte", remove nothing)
    base_payload[0]["options"][0]["attributes"].append({"title": "Matte", "sort_order": 2})
    r = await client.post(
        f"/api/ingest/{seed_supplier.id}/products",
        headers=SECRET,
        json=base_payload,
    )
    assert r.status_code == 200

    prod = (await db.execute(
        select(Product).where(Product.supplier_sku == "OPT-TEST-2")
    )).scalar_one()
    opts = (await db.execute(
        select(ProductOption).where(ProductOption.product_id == prod.id)
    )).scalars().all()
    assert len(opts) == 1

    attrs = (await db.execute(
        select(ProductOptionAttribute).where(
            ProductOptionAttribute.product_option_id == opts[0].id
        )
    )).scalars().all()
    assert len(attrs) == 3
    assert {a.title for a in attrs} == {"None", "Gloss", "Matte"}
```

- [ ] **Step 4: Run tests to verify they fail (expected — ingest logic not written yet)**

Run: `docker compose exec -T api sh -c "cd /app && python -m pytest tests/test_catalog_ingest.py::test_ingest_products_creates_options tests/test_catalog_ingest.py::test_ingest_products_options_idempotent -v"`
Expected: Both FAIL with `422` or `KeyError` — `options` field not handled yet.

- [ ] **Step 5: Stage**

```bash
git add backend/tests/test_catalog_ingest.py
# suggested: test(ingest): add failing tests for product options + attributes
```

---

## Task 5: Backend ingest — upsert options + attributes

**Files:**
- Modify: `backend/modules/catalog/ingest.py`

- [ ] **Step 1: Add new model imports**

In `ingest.py` line 24, change:
```python
from .models import Category, Product, ProductImage, ProductVariant
```
to:
```python
from .models import Category, Product, ProductImage, ProductOption, ProductOptionAttribute, ProductVariant
```

- [ ] **Step 2: Add new schema imports**

In `ingest.py` line 25–31, change:
```python
from .schemas import (
    CategoryIngest,
    IngestResult,
    InventoryIngest,
    PriceIngest,
    ProductIngest,
)
```
to:
```python
from .schemas import (
    CategoryIngest,
    IngestResult,
    InventoryIngest,
    OptionIngest,
    PriceIngest,
    ProductIngest,
)
```

- [ ] **Step 3: Add `_upsert_options` helper function**

Add before `ingest_categories` (before line 86):

```python
async def _upsert_options(
    db: AsyncSession, product_id: uuid_mod.UUID, options: list[OptionIngest]
) -> None:
    """Upsert product_options by (product_id, option_key).
    Attributes are delete-and-reinsert per option (titles can change between syncs).
    Only runs when options list is non-empty.
    """
    import json as _json

    for opt in options:
        # Upsert the option row
        opt_stmt = pg_insert(ProductOption).values(
            product_id=product_id,
            option_key=opt.option_key,
            title=opt.title,
            options_type=opt.options_type,
            sort_order=opt.sort_order,
            master_option_id=opt.master_option_id,
            ops_option_id=opt.ops_option_id,
            required=opt.required,
            status=1,
        ).on_conflict_do_update(
            index_elements=["product_id", "option_key"],
            set_={
                "title": opt.title,
                "options_type": opt.options_type,
                "sort_order": opt.sort_order,
                "master_option_id": opt.master_option_id,
                "ops_option_id": opt.ops_option_id,
                "required": opt.required,
            },
        ).returning(ProductOption.id)
        option_id = (await db.execute(opt_stmt)).scalar_one()

        # Normalize attributes — OPS may return a JSON string scalar
        raw_attrs = opt.attributes
        if isinstance(raw_attrs, str):
            try:
                raw_attrs = _json.loads(raw_attrs)
            except Exception:
                raw_attrs = []

        if not raw_attrs:
            continue

        # Delete existing attributes and re-insert fresh set
        await db.execute(
            ProductOptionAttribute.__table__.delete().where(
                ProductOptionAttribute.product_option_id == option_id
            )
        )
        for attr in raw_attrs:
            title = attr.title if hasattr(attr, "title") else (attr.get("title") if isinstance(attr, dict) else str(attr))
            sort_order = attr.sort_order if hasattr(attr, "sort_order") else (attr.get("sort_order", 0) if isinstance(attr, dict) else 0)
            ops_attribute_id = getattr(attr, "ops_attribute_id", None) or (attr.get("ops_attribute_id") if isinstance(attr, dict) else None)
            if not title:
                continue
            db.add(ProductOptionAttribute(
                product_option_id=option_id,
                title=title,
                sort_order=sort_order,
                ops_attribute_id=ops_attribute_id,
                status=1,
            ))
```

- [ ] **Step 4: Call `_upsert_options` inside `ingest_products`**

In `ingest_products`, after the images loop (after line 248, before `await _finish_sync_job`):

```python
        if item.options:
            await _upsert_options(db, product_id, item.options)
```

The full context around the insertion point:
```python
        for idx, img in enumerate(item.images):
            image_stmt = pg_insert(ProductImage).values(
                ...
            )
            await db.execute(image_stmt)

        if item.options:                                          # ← ADD THIS
            await _upsert_options(db, product_id, item.options)  # ← ADD THIS

    await _finish_sync_job(db, job, len(batch))
```

- [ ] **Step 5: Add `uuid_mod` import if missing**

`ingest.py` uses `UUID` from `uuid` directly. `_upsert_options` uses `uuid_mod.UUID`. Add at top of file if not present:
```python
import uuid as uuid_mod
```

Check: `grep "^import uuid" backend/modules/catalog/ingest.py` — if absent, add it after `import os`.

- [ ] **Step 6: Run failing tests — expect PASS now**

Run: `docker compose exec -T api sh -c "cd /app && python -m pytest tests/test_catalog_ingest.py::test_ingest_products_creates_options tests/test_catalog_ingest.py::test_ingest_products_options_idempotent -v"`
Expected: Both PASS.

- [ ] **Step 7: Run full suite to catch regressions**

Run: `docker compose exec -T api sh -c "cd /app && python -m pytest tests/test_catalog_ingest.py -v"`
Expected: All pass (12 prior + 2 new = 14 total).

- [ ] **Step 8: Stage**

```bash
git add backend/modules/catalog/ingest.py
# suggested: feat(ingest): upsert product options + attributes per product
```

---

## Task 6: Route — eager-load options on PDP endpoint

**Files:**
- Modify: `backend/modules/catalog/routes.py:12-13,111-114`

- [ ] **Step 1: Add `ProductOption` to model imports**

Line 12:
```python
from .models import Category, Product, ProductVariant
```
Change to:
```python
from .models import Category, Product, ProductOption, ProductVariant
```

- [ ] **Step 2: Add `selectinload` for options in `get_product`**

Lines 111–114 currently:
```python
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
        )
```
Change to:
```python
        .options(
            selectinload(Product.variants),
            selectinload(Product.images),
            selectinload(Product.options).selectinload(ProductOption.attributes),
        )
```

- [ ] **Step 3: Smoke test**

Run:
```bash
PRODUCT_ID=$(docker compose exec -T postgres psql -U vg_user -d vg_hub -t -c "select id from products limit 1" | tr -d ' \n')
curl -s "http://localhost:8000/api/products/${PRODUCT_ID}" | python -m json.tool | grep -A2 '"options"'
```
Expected: `"options": []` (no options yet — empty array is correct, products haven't been re-ingested with options).

- [ ] **Step 4: Stage**

```bash
git add backend/modules/catalog/routes.py
# suggested: feat(catalog): eager-load product options on get_product
```

---

## Task 7: Frontend types

**Files:**
- Modify: `frontend/src/lib/types.ts:65-81`

- [ ] **Step 1: Add `ProductOptionAttribute` and `ProductOption` interfaces**

In `frontend/src/lib/types.ts`, before the `Product` interface (before line 65), add:

```typescript
export interface ProductOptionAttribute {
  id: string;
  title: string;
  sort_order: number;
  ops_attribute_id: number | null;
}

export interface ProductOption {
  id: string;
  option_key: string;
  title: string;
  options_type: string | null;
  sort_order: number;
  master_option_id: number | null;
  ops_option_id: number | null;
  required: boolean;
  attributes: ProductOptionAttribute[];
}
```

- [ ] **Step 2: Extend `Product` interface with `options`**

In the `Product` interface, after `images: ProductImage[];` (line 80), add:

```typescript
  options: ProductOption[];
```

- [ ] **Step 3: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 4: Stage**

```bash
git add frontend/src/lib/types.ts
# suggested: feat(types): add ProductOption + ProductOptionAttribute to Product
```

---

## Task 8: PDP — render options section

**Files:**
- Modify: `frontend/src/app/storefront/vg/product/[product_id]/page.tsx`

- [ ] **Step 1: Add options section to `info` JSX**

In `page.tsx`, the `info` block starts at line 73. Insert after the `VariantPicker` block (after line 99, before the button row at line 101):

```tsx
      {product.options && product.options.length > 0 && (
        <div className="py-5 border-t border-dashed border-[#cfccc8]">
          <div className="text-[11px] font-bold uppercase tracking-[0.12em] text-[#888894] mb-3">
            Product Options
          </div>
          <div className="flex flex-col gap-2">
            {[...product.options]
              .sort((a, b) => a.sort_order - b.sort_order)
              .filter((opt) => opt.attributes.length > 0)
              .map((opt) => (
                <div key={opt.id} className="flex gap-2 text-[12.5px]">
                  <span className="font-semibold text-[#484852] w-[140px] shrink-0 truncate">
                    {opt.title}
                  </span>
                  <span className="text-[#888894] font-mono">
                    {opt.attributes
                      .sort((a, b) => a.sort_order - b.sort_order)
                      .map((a) => a.title)
                      .join(" · ")}
                  </span>
                </div>
              ))}
          </div>
        </div>
      )}
```

- [ ] **Step 2: TypeScript check**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 3: Stage**

```bash
git add "frontend/src/app/storefront/vg/product/[product_id]/page.tsx"
# suggested: feat(pdp): render product options section
```

---

## Task 9: End-to-end verification

- [ ] **Step 1: Run full backend test suite**

Run: `docker compose exec -T api sh -c "cd /app && python -m pytest -q"`
Expected: All green. 2 new option tests pass (14 total in `test_catalog_ingest.py`).

- [ ] **Step 2: Test ingest with options payload via curl**

Run:
```bash
SUPPLIER_ID=$(docker compose exec -T postgres psql -U vg_user -d vg_hub -t -c "select id from suppliers limit 1" | tr -d ' \n')
SECRET=$(grep INGEST_SHARED_SECRET .env | cut -d= -f2)
curl -s -X POST "http://localhost:8000/api/ingest/${SUPPLIER_ID}/products" \
  -H "Content-Type: application/json" \
  -H "X-Ingest-Secret: ${SECRET}" \
  -d '[{"supplier_sku":"SMOKE-OPT-1","product_name":"Smoke Options Test","options":[{"option_key":"inkFinish","title":"Ink Finish","options_type":"Radio Button","sort_order":0,"required":false,"attributes":[{"title":"Gloss","sort_order":0},{"title":"Matte","sort_order":1}]}]}]'
```
Expected: `{"sync_job_id":"...","records_processed":1,"status":"completed"}`

- [ ] **Step 3: Verify API returns options**

Run:
```bash
PRODUCT_ID=$(docker compose exec -T postgres psql -U vg_user -d vg_hub -t -c "select id from products where supplier_sku='SMOKE-OPT-1' limit 1" | tr -d ' \n')
curl -s "http://localhost:8000/api/products/${PRODUCT_ID}" | python -m json.tool | grep -A 20 '"options"'
```
Expected: `"options"` array with one entry having `"option_key": "inkFinish"` and `"attributes"` with Gloss + Matte.

- [ ] **Step 4: Frontend typecheck**

Run: `cd frontend && npx tsc --noEmit`
Expected: No errors.

- [ ] **Step 5: Rebuild Docker frontend (if running containerized)**

Run: `docker compose build frontend && docker compose up -d frontend`
Expected: Container starts, `/storefront/vg` returns 200.

---

## Self-Review Notes

**Spec coverage:**
- ✅ n8n node fix (Task 1)
- ✅ `ProductOption` + `ProductOptionAttribute` models (Task 2)
- ✅ Ingest schemas (Task 3)
- ✅ Ingest tests — TDD (Task 4 writes tests, Task 5 implements)
- ✅ Ingest logic (Task 5)
- ✅ Route eager-load (Task 6)
- ✅ Frontend types (Task 7)
- ✅ PDP render (Task 8)
- ✅ E2E verification (Task 9)

**Type consistency:**
- `ProductOption` / `ProductOptionRead` / `ProductOption` (TS) — same shape throughout
- `OptionIngest.attributes: list[OptionAttributeIngest]` matches `_upsert_options` handler
- `product_option_id` (FK column) consistently named in both models

**No placeholders:** All steps contain complete code.
