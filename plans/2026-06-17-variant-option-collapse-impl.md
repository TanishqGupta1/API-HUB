# Variant → Option Collapse Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only idempotent pass that turns a product's stored
`product_variants` (color × size matrix) into two selectable `ProductOption`s
("Color" swatch, "Size" dropdown), so one supplier style is one product with
options instead of N products.

**Architecture:** New `modules/catalog/option_collapse.py` reads variants and
writes the two derived options via the existing `_upsert_options`, then prunes
any derived option whose axis went empty. Variants are never mutated. No
`product_sizes` written (that table is physical width/height for print — wrong
for apparel S/M/L; see design doc). OPS-binding id fields stay null (graphx/push
fills later).

**Tech Stack:** Python 3.12, FastAPI, async SQLAlchemy + asyncpg, pytest /
pytest-asyncio. Backend root: `api-hub/api-hub/backend` (note nested path).

**Design doc:** `plans/2026-06-16-variant-option-collapse.md`

---

## File Structure

- **Modify** `backend/modules/catalog/schemas.py` — add `enabled` to `OptionIngest`.
- **Modify** `backend/modules/catalog/ingest.py` — `_upsert_options` writes `enabled`.
- **Create** `backend/modules/catalog/option_collapse.py` — helpers + `derive_options` + `derive_options_bulk`.
- **Modify** `backend/modules/catalog/routes.py` — two trigger routes.
- **Create** `backend/tests/test_option_collapse.py` — full test suite.

Verified facts (against current code):
- `product_options` unique = `uq_product_option_key (product_id, option_key)` (models.py:127) → `_upsert_options` ON CONFLICT valid.
- `_upsert_options` upserts + delete-reinserts attrs but does NOT prune options, and never sets `enabled` (default `False`, models.py:142) (ingest.py:116-181).
- `ProductOptionAttribute` FK `ondelete="CASCADE"` (models.py:161) → deleting an option drops its attributes.
- `ProductVariant.color` / `.size` both nullable `String` (models.py:89-90).
- Test fixtures: `db` (AsyncSession), `seed_supplier`, `client` (conftest.py:192-209).

---

## Task 1: Add `enabled` to `OptionIngest` and persist it

**Files:**
- Modify: `backend/modules/catalog/schemas.py:241-250`
- Modify: `backend/modules/catalog/ingest.py:124-150`
- Test: `backend/tests/test_option_collapse.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_option_collapse.py`:

```python
"""Tests for the variant→option collapse pass."""
import pytest
from sqlalchemy import select

from modules.catalog.models import (
    Product,
    ProductVariant,
    ProductOption,
    ProductOptionAttribute,
)


async def _mk_product(db, supplier, variants, sku="PC54", name="Core Tee"):
    """Create a product + variants. `variants` = list of (color, size) tuples."""
    p = Product(supplier_id=supplier.id, supplier_sku=sku, product_name=name)
    db.add(p)
    await db.commit()
    await db.refresh(p)
    for color, size in variants:
        db.add(
            ProductVariant(
                product_id=p.id, color=color, size=size,
                part_id=f"{color or 'x'}-{size or 'x'}",
            )
        )
    await db.commit()
    return p


async def _options(db, product_id):
    rows = (
        await db.execute(
            select(ProductOption).where(ProductOption.product_id == product_id)
        )
    ).scalars().all()
    return {o.option_key: o for o in rows}


async def _attrs(db, option_id):
    return (
        await db.execute(
            select(ProductOptionAttribute)
            .where(ProductOptionAttribute.product_option_id == option_id)
            .order_by(ProductOptionAttribute.sort_order)
        )
    ).scalars().all()


@pytest.mark.asyncio
async def test_optioningest_has_enabled_field():
    from modules.catalog.schemas import OptionIngest

    o = OptionIngest(option_key="color", title="Color")
    assert o.enabled is False  # backward-compatible default
    o2 = OptionIngest(option_key="color", title="Color", enabled=True)
    assert o2.enabled is True


@pytest.mark.asyncio
async def test_upsert_options_persists_enabled(db, seed_supplier):
    from modules.catalog.ingest import _upsert_options
    from modules.catalog.schemas import OptionIngest, OptionAttributeIngest

    p = await _mk_product(db, seed_supplier, [])
    await _upsert_options(
        db, p.id,
        [OptionIngest(
            option_key="color", title="Color", enabled=True,
            attributes=[OptionAttributeIngest(title="Red", attribute_key="red")],
        )],
    )
    await db.commit()
    opts = await _options(db, p.id)
    assert opts["color"].enabled is True
```

- [ ] **Step 2: Run, verify fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_option_collapse.py -v`
Expected: FAIL — `OptionIngest` has no `enabled` (TypeError / assertion).

- [ ] **Step 3: Add the field**

In `schemas.py`, inside `class OptionIngest(BaseModel)` (after `required: bool = False`, before the `attributes` field):

```python
    enabled: bool = False
```

- [ ] **Step 4: Persist it in `_upsert_options`**

In `ingest.py`, in the `pg_insert(ProductOption).values(...)` block add `enabled=opt.enabled,` after `required=opt.required,`; in the `.on_conflict_do_update(... set_={...})` add `"enabled": opt.enabled,` after `"required": opt.required,`. Resulting values block:

```python
            .values(
                product_id=product_id,
                option_key=opt.option_key,
                title=opt.title,
                options_type=opt.options_type,
                sort_order=opt.sort_order,
                master_option_id=opt.master_option_id,
                ops_option_id=opt.ops_option_id,
                required=opt.required,
                enabled=opt.enabled,
                status=1,
            )
            .on_conflict_do_update(
                index_elements=["product_id", "option_key"],
                set_={
                    "title": opt.title,
                    "options_type": opt.options_type,
                    "sort_order": opt.sort_order,
                    "master_option_id": opt.master_option_id,
                    "ops_option_id": opt.ops_option_id,
                    "required": opt.required,
                    "enabled": opt.enabled,
                },
            )
```

- [ ] **Step 5: Run, verify pass**

Run: `pytest tests/test_option_collapse.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/modules/catalog/schemas.py backend/modules/catalog/ingest.py backend/tests/test_option_collapse.py
git commit -m "feat(catalog): OptionIngest.enabled + persist in _upsert_options"
```

---

## Task 2: Pure helpers — normalize, slug, distinct, size order

**Files:**
- Create: `backend/modules/catalog/option_collapse.py`
- Test: `backend/tests/test_option_collapse.py`

- [ ] **Step 1: Write failing tests**

Append to `test_option_collapse.py`:

```python
@pytest.mark.no_db
def test_distinct_normalizes_and_dedups():
    from modules.catalog.option_collapse import _distinct
    # "Red"/"RED "/"red" collapse to one; first display form wins; alpha sort
    assert _distinct(["Navy", "Red", "RED ", "red", None, "  "]) == ["Navy", "Red"]


@pytest.mark.no_db
def test_size_sort_order():
    from modules.catalog.option_collapse import _distinct, _size_sort_key
    out = _distinct(["XL", "S", "2XL", "M", "L", "XS"], sort_key=_size_sort_key)
    assert out == ["XS", "S", "M", "L", "XL", "2XL"]


@pytest.mark.no_db
def test_slug():
    from modules.catalog.option_collapse import _slug
    assert _slug("Forest Green") == "forest-green"
    assert _slug("  Heather/Grey ") == "heather-grey"
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/test_option_collapse.py -k "distinct or size_sort or slug" -v`
Expected: FAIL — module `option_collapse` does not exist.

- [ ] **Step 3: Create the module with helpers**

Create `backend/modules/catalog/option_collapse.py`:

```python
"""Derive selectable Color/Size options from a product's stored variant matrix.

Read-only over product_variants; never mutates variants. Idempotent full-replace
of the two derived ProductOptions (option_key 'color', 'size'). No product_sizes
written. See plans/2026-06-16-variant-option-collapse.md.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Optional
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .ingest import _upsert_options
from .models import Product, ProductOption, ProductVariant
from .schemas import OptionAttributeIngest, OptionIngest

DERIVED_OPTION_KEYS = ("color", "size")

# Canonical apparel size order; lower = earlier. Unknown sizes sort after, alpha.
_SIZE_ORDER = {
    "XS": 0, "S": 1, "M": 2, "L": 3, "XL": 4,
    "2XL": 5, "XXL": 5, "3XL": 6, "XXXL": 6,
    "4XL": 7, "5XL": 8, "6XL": 9,
}


@dataclass
class CollapseResult:
    colors: int        # 1 if a color option was written, else 0
    sizes: int         # 1 if a size option was written, else 0
    color_attrs: int   # distinct color count
    size_attrs: int    # distinct size count


def _norm(value: str) -> str:
    """Trim + collapse internal whitespace. Preserves display casing."""
    return re.sub(r"\s+", " ", value).strip()


def _slug(value: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", _norm(value).casefold()).strip("-")
    return s or "x"


def _size_sort_key(title: str):
    key = _norm(title).upper()
    return (_SIZE_ORDER.get(key, 999), key)


def _distinct(
    values: Iterable[Optional[str]],
    sort_key: Optional[Callable[[str], object]] = None,
) -> list[str]:
    """Ordered distinct, dedup on casefold key; first display form wins."""
    seen: dict[str, str] = {}
    for v in values:
        if v is None:
            continue
        disp = _norm(v)
        if not disp:
            continue
        k = disp.casefold()
        if k not in seen:
            seen[k] = disp
    items = list(seen.values())
    items.sort(key=sort_key if sort_key else (lambda s: s.casefold()))
    return items
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/test_option_collapse.py -k "distinct or size_sort or slug" -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/modules/catalog/option_collapse.py backend/tests/test_option_collapse.py
git commit -m "feat(catalog): option_collapse helpers (normalize/slug/distinct/size-order)"
```

---

## Task 3: `derive_options` core — build + persist Color/Size options

**Files:**
- Modify: `backend/modules/catalog/option_collapse.py`
- Test: `backend/tests/test_option_collapse.py`

- [ ] **Step 1: Write failing tests**

Append:

```python
def _matrix(colors, sizes):
    return [(c, s) for c in colors for s in sizes]


@pytest.mark.asyncio
async def test_matrix_collapse(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    colors = ["Red", "Navy", "Black", "White", "Royal", "Green", "Maroon", "Gold"]
    sizes = ["S", "M", "L", "XL", "2XL", "3XL"]
    p = await _mk_product(db, seed_supplier, _matrix(colors, sizes))  # 48 variants

    res = await derive_options(db, p.id)

    assert (res.colors, res.sizes) == (1, 1)
    assert (res.color_attrs, res.size_attrs) == (8, 6)
    opts = await _options(db, p.id)
    assert set(opts) == {"color", "size"}
    assert opts["color"].options_type == "swatch"
    assert opts["size"].options_type == "dropdown"
    assert len(await _attrs(db, opts["color"].id)) == 8
    assert len(await _attrs(db, opts["size"].id)) == 6
    # no product_sizes written
    from modules.catalog.models import ProductSize
    sizes_rows = (await db.execute(
        select(ProductSize).where(ProductSize.product_id == p.id)
    )).scalars().all()
    assert sizes_rows == []


@pytest.mark.asyncio
async def test_enabled_and_status_set(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", "M")])
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    for o in opts.values():
        assert o.enabled is True
        assert o.status == 1


@pytest.mark.asyncio
async def test_required_symmetric(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", "M"), ("Navy", "L")])
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    assert opts["color"].required is True
    assert opts["size"].required is True


@pytest.mark.asyncio
async def test_normalize_then_dedup(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", "M"), ("RED ", "M"), ("red", "M")])
    res = await derive_options(db, p.id)
    assert res.color_attrs == 1  # one color, no uq_option_attribute_title violation


@pytest.mark.asyncio
async def test_mixed_nulls(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", None), (None, "M"), ("Navy", "L")])
    res = await derive_options(db, p.id)
    assert res.color_attrs == 2  # Red, Navy
    assert res.size_attrs == 2   # M, L


@pytest.mark.asyncio
async def test_size_ordering_persisted(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", s) for s in ["XL", "S", "2XL", "M"]])
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    titles = [a.title for a in await _attrs(db, opts["size"].id)]
    assert titles == ["S", "M", "XL", "2XL"]


@pytest.mark.asyncio
async def test_noop_when_no_color_or_size(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [(None, None), (None, None)])
    res = await derive_options(db, p.id)
    assert (res.colors, res.sizes) == (0, 0)
    assert await _options(db, p.id) == {}


@pytest.mark.asyncio
async def test_idempotent(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, _matrix(["Red", "Navy"], ["S", "M"]))
    r1 = await derive_options(db, p.id)
    r2 = await derive_options(db, p.id)
    assert (r1.color_attrs, r1.size_attrs) == (r2.color_attrs, r2.size_attrs) == (2, 2)
    opts = await _options(db, p.id)
    assert len(await _attrs(db, opts["color"].id)) == 2
    assert len(await _attrs(db, opts["size"].id)) == 2
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/test_option_collapse.py -k "matrix or enabled or required or normalize or mixed or ordering or noop or idempotent" -v`
Expected: FAIL — `derive_options` not defined.

- [ ] **Step 3: Implement `derive_options` + `_build_option`**

Append to `option_collapse.py`:

```python
def _build_option(
    option_key: str,
    title: str,
    options_type: str,
    raw_titles: Iterable[Optional[str]],
    sort_order: int,
    sort_key: Optional[Callable[[str], object]] = None,
) -> tuple[OptionIngest, int]:
    distinct = _distinct(raw_titles, sort_key=sort_key)
    attrs = [
        OptionAttributeIngest(title=t, attribute_key=_slug(t), sort_order=i)
        for i, t in enumerate(distinct)
    ]
    opt = OptionIngest(
        option_key=option_key,
        title=title,
        options_type=options_type,
        sort_order=sort_order,
        required=bool(distinct),
        enabled=True,
        attributes=attrs,
    )
    return opt, len(distinct)


async def derive_options(db: AsyncSession, product_id: UUID) -> CollapseResult:
    """Read variants, (re)build Color/Size options, prune emptied axes. Commits."""
    rows = (
        await db.execute(
            select(ProductVariant.color, ProductVariant.size)
            .where(ProductVariant.product_id == product_id)
        )
    ).all()

    color_opt, n_colors = _build_option(
        "color", "Color", "swatch", (r.color for r in rows), sort_order=0
    )
    size_opt, n_sizes = _build_option(
        "size", "Size", "dropdown", (r.size for r in rows),
        sort_order=1, sort_key=_size_sort_key,
    )

    payload: list[OptionIngest] = []
    built: set[str] = set()
    if n_colors:
        payload.append(color_opt)
        built.add("color")
    if n_sizes:
        payload.append(size_opt)
        built.add("size")

    if payload:
        await _upsert_options(db, product_id, payload)

    stale = [k for k in DERIVED_OPTION_KEYS if k not in built]
    if stale:
        await db.execute(
            delete(ProductOption).where(
                ProductOption.product_id == product_id,
                ProductOption.option_key.in_(stale),
            )
        )

    await db.commit()
    return CollapseResult(
        colors=1 if n_colors else 0,
        sizes=1 if n_sizes else 0,
        color_attrs=n_colors,
        size_attrs=n_sizes,
    )
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/test_option_collapse.py -v`
Expected: PASS (all tests so far).

- [ ] **Step 5: Commit**

```bash
git add backend/modules/catalog/option_collapse.py backend/tests/test_option_collapse.py
git commit -m "feat(catalog): derive_options — collapse variant matrix to Color/Size options"
```

---

## Task 4: Prune on axis-emptied between runs

**Files:**
- Test: `backend/tests/test_option_collapse.py` (logic already in Task 3 prune branch)

- [ ] **Step 1: Write failing tests**

Append:

```python
@pytest.mark.asyncio
async def test_prune_removed_color(db, seed_supplier):
    """8 colors then 6 — the 2 dropped colors disappear."""
    from modules.catalog.option_collapse import derive_options
    eight = ["Red", "Navy", "Black", "White", "Royal", "Green", "Maroon", "Gold"]
    p = await _mk_product(db, seed_supplier, [(c, "M") for c in eight])
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    assert len(await _attrs(db, opts["color"].id)) == 8

    # delete 2 colors' variants, re-derive
    await db.execute(
        delete(ProductVariant).where(
            ProductVariant.product_id == p.id,
            ProductVariant.color.in_(["Maroon", "Gold"]),
        )
    )
    await db.commit()
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    assert len(await _attrs(db, opts["color"].id)) == 6


@pytest.mark.asyncio
async def test_prune_axis_emptied(db, seed_supplier):
    """Color option removed entirely when all color variants gone."""
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red", "M"), ("Navy", "L")])
    await derive_options(db, p.id)
    assert "color" in await _options(db, p.id)

    # null out all colors, re-derive → color option pruned, size stays
    await db.execute(
        ProductVariant.__table__.update()
        .where(ProductVariant.product_id == p.id)
        .values(color=None)
    )
    await db.commit()
    await derive_options(db, p.id)
    opts = await _options(db, p.id)
    assert "color" not in opts
    assert "size" in opts
```

- [ ] **Step 2: Run, verify pass**

Run: `pytest tests/test_option_collapse.py -k prune -v`
Expected: PASS — prune branch from Task 3 handles both (attrs delete-reinsert covers the 8→6 case; the `stale` delete covers the emptied-axis case; cascade drops orphan attrs).

> If `test_prune_axis_emptied` fails because the size option's `sort_order`
> shifted, that's fine — assert only on key presence as written.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_option_collapse.py
git commit -m "test(catalog): prune coverage for removed/emptied option axes"
```

---

## Task 5: `derive_options_bulk` backfill

**Files:**
- Modify: `backend/modules/catalog/option_collapse.py`
- Test: `backend/tests/test_option_collapse.py`

- [ ] **Step 1: Write failing test**

Append:

```python
@pytest.mark.asyncio
async def test_bulk_backfill_one_supplier(db, seed_supplier):
    from modules.catalog.option_collapse import derive_options_bulk
    await _mk_product(db, seed_supplier, [("Red", "M")], sku="A", name="A")
    await _mk_product(db, seed_supplier, [("Navy", "L"), ("Navy", "XL")], sku="B", name="B")

    totals = await derive_options_bulk(db, supplier_id=seed_supplier.id)

    assert totals["products"] == 2
    assert totals["color_options"] == 2
    assert totals["size_options"] == 2
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/test_option_collapse.py -k bulk -v`
Expected: FAIL — `derive_options_bulk` not defined.

- [ ] **Step 3: Implement**

Append to `option_collapse.py`:

```python
async def derive_options_bulk(
    db: AsyncSession, supplier_id: Optional[UUID] = None
) -> dict:
    """Re-derive options for every product (optionally one supplier). Commits per
    product so one bad product does not roll back the whole run."""
    q = select(Product.id)
    if supplier_id is not None:
        q = q.where(Product.supplier_id == supplier_id)
    ids = (await db.execute(q)).scalars().all()

    totals = {"products": 0, "color_options": 0, "size_options": 0}
    for pid in ids:
        res = await derive_options(db, pid)
        totals["products"] += 1
        totals["color_options"] += res.colors
        totals["size_options"] += res.sizes
    return totals
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/test_option_collapse.py -k bulk -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/catalog/option_collapse.py backend/tests/test_option_collapse.py
git commit -m "feat(catalog): derive_options_bulk backfill"
```

---

## Task 6: Trigger routes

**Files:**
- Modify: `backend/modules/catalog/routes.py`
- Test: `backend/tests/test_option_collapse.py`

> **Route ordering:** register the bulk literal route `POST /derive-options`
> BEFORE the param route `POST /{product_id}/derive-options` so the literal is
> not shadowed by a path-param match. Both live on the existing `router`
> (prefix `/api/products`). Routes use `CurrentUser` (already imported) — JWT;
> the test `client` fixture injects a mock vg_admin (conftest.py).

- [ ] **Step 1: Write failing test**

Append:

```python
@pytest.mark.asyncio
async def test_route_derive_single_product(client, db, seed_supplier):
    p = await _mk_product(db, seed_supplier, [("Red", "M"), ("Navy", "L")])
    r = await client.post(f"/api/products/{p.id}/derive-options")
    assert r.status_code == 200
    body = r.json()
    assert body["colors"] == 1 and body["sizes"] == 1
    assert body["color_attrs"] == 2 and body["size_attrs"] == 2


@pytest.mark.asyncio
async def test_route_derive_bulk(client, db, seed_supplier):
    await _mk_product(db, seed_supplier, [("Red", "M")], sku="A", name="A")
    r = await client.post(f"/api/products/derive-options?supplier_id={seed_supplier.id}")
    assert r.status_code == 200
    assert r.json()["products"] >= 1
```

- [ ] **Step 2: Run, verify fail**

Run: `pytest tests/test_option_collapse.py -k route -v`
Expected: FAIL — 404 (routes not registered).

- [ ] **Step 3: Add routes**

In `routes.py`, add the import near the other `.` imports:

```python
from .option_collapse import derive_options, derive_options_bulk
```

Then add (bulk route FIRST, before any `/{product_id}` param route in this file):

```python
@router.post("/derive-options")
async def derive_all_product_options(
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    supplier_id: Optional[UUID] = Query(default=None),
):
    """Backfill: (re)derive Color/Size options for all products (or one supplier)."""
    return await derive_options_bulk(db, supplier_id)


@router.post("/{product_id}/derive-options")
async def derive_product_options(
    product_id: UUID,
    _user: CurrentUser,
    db: AsyncSession = Depends(get_db),
):
    """(Re)derive Color/Size options for one product from its variant matrix."""
    res = await derive_options(db, product_id)
    return {
        "product_id": str(product_id),
        "colors": res.colors,
        "sizes": res.sizes,
        "color_attrs": res.color_attrs,
        "size_attrs": res.size_attrs,
    }
```

- [ ] **Step 4: Run, verify pass**

Run: `pytest tests/test_option_collapse.py -k route -v`
Expected: PASS.

- [ ] **Step 5: Full suite + commit**

Run: `pytest tests/test_option_collapse.py -v`
Expected: PASS (all).

```bash
git add backend/modules/catalog/routes.py backend/tests/test_option_collapse.py
git commit -m "feat(catalog): routes to trigger variant→option collapse (single + bulk)"
```

---

## Task 7: Backfill the 994 existing products (manual, post-merge)

- [ ] **Step 1:** Merge the branch and deploy.
- [ ] **Step 2:** Run the bulk backfill against live data (authenticated as vg_admin):

```bash
curl -X POST "$API/api/products/derive-options" -H "Authorization: Bearer $TOKEN"
```

Expected JSON: `{"products": <~994>, "color_options": N, "size_options": M}`.

- [ ] **Step 3:** Spot-check 2-3 known SanMar styles in the UI/DB: one `color`
  option + one `size` option, attribute counts match the style's color/size
  spread, `enabled=true`.

---

## Self-Review notes

- **Spec coverage:** every design-doc section maps to a task — schemas/enabled
  (T1), helpers+normalize-dedup (T2), color+size build / required-symmetry /
  enabled / no product_sizes / ordering / no-op / idempotency (T3), prune (T4),
  bulk (T5), routes (T6), backfill (T7).
- **Placeholders:** none — all steps carry full code + exact commands.
- **Type consistency:** `derive_options`, `derive_options_bulk`, `_build_option`,
  `_distinct`, `_slug`, `_size_sort_key`, `CollapseResult`, `DERIVED_OPTION_KEYS`,
  `OptionIngest.enabled` referenced consistently across tasks.
- **Out of scope (unchanged):** no OPS push, no graphx ingest, no `product_sizes`
  write, no normalizer edit, no price movement, no multi-tenant overrides.
