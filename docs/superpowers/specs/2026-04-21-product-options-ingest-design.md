# Product Options Ingest — Design Spec

**Date:** 2026-04-21
**Scope:** Ingest VG product additional options (master-option-derived) into API Hub catalog DB + display on PDP. Prerequisite for customer push (Spec 4).
**Context:** Christian call 2026-04-21 — VG products are options-driven (not variant-driven). Current ingest captures zero option data.

---

## Problem

`/api/ingest/{supplier_id}/products` stores variants + images but ignores `product_additional_options` from OPS. The storefront PDP shows no options. Customer push (future) cannot build option mappings without this data in the DB.

---

## Supplier Types (Architecture Context)

Two source types converge in the API Hub catalog:

| Type | Example | Source data |
|---|---|---|
| `ops_internal` | VG | Products with master options (OPS GraphQL) |
| `promo_standards` | SanMar, S&S | Products with size/color variants (SOAP/REST) |

This spec covers `ops_internal` only. PromoStandards variants already handled via `ProductVariant`.

---

## Scope

### In scope
- Fix `OnPrintShop.node.ts`: add 4 missing fields to `productAdditionalOptionsFields`
- `ProductOption` + `ProductOptionAttribute` DB models
- Ingest endpoint: parse + upsert options per product
- `ProductRead` schema: expose `options[]`
- PDP: read-only display of option groups + values
- 2 new ingest behavior tests

### Out of scope
- Customer push (option mapping, `setAdditionalOption`) — Spec 4
- `setAdditionalOptionAttributes`, `setProductsAttributePrice` — Spec 4
- PromoStandards variant→option conversion — Spec 4
- External availability flag — Spec 3 (waiting on OPS team)
- Option pricing, formula, rules — Spec 4

---

## 1. n8n Node Fix

File: `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts`

`productAdditionalOptionsFields` currently exposes 4 fields:
```
option_key, options_type, required, sort_order
```

Add 4 missing fields to the `options` array in that multiOptions config:
```typescript
{ name: 'Product Additional Option ID', value: 'product_additional_option_id' },
{ name: 'Master Option ID',             value: 'master_option_id' },
{ name: 'Title',                        value: 'title' },
{ name: 'Attributes',                   value: 'attributes' },
```

Update `default` array to include all 8 fields:
```typescript
default: [
  'product_additional_option_id',
  'master_option_id',
  'option_key',
  'title',
  'options_type',
  'required',
  'sort_order',
  'attributes',
],
```

`attributes` is a JSON scalar from OPS — returned as-is, parsed in FastAPI ingest.

---

## 2. Data Model

File: `backend/modules/catalog/models.py`

```python
class ProductOption(Base):
    __tablename__ = "product_options"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_id       = Column(UUID(as_uuid=True), ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    ops_option_id    = Column(Integer, nullable=True)   # OPS product_additional_option_id
    master_option_id = Column(Integer, nullable=True)   # VG master_option_id; null = product-specific
    option_key       = Column(String, nullable=False)   # "inkFinish"
    title            = Column(String, nullable=False)   # "Ink Finish"
    options_type     = Column(String, nullable=True)    # "Radio Button" | "Drop Down"
    sort_order       = Column(Integer, default=0)
    required         = Column(Boolean, default=False)
    status           = Column(Integer, default=1)

    product    = relationship("Product", back_populates="options")
    attributes = relationship("ProductOptionAttribute", back_populates="option", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("product_id", "option_key", name="uq_product_option_key"),)


class ProductOptionAttribute(Base):
    __tablename__ = "product_option_attributes"

    id                = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    product_option_id = Column(UUID(as_uuid=True), ForeignKey("product_options.id", ondelete="CASCADE"), nullable=False)
    ops_attribute_id  = Column(Integer, nullable=True)
    title             = Column(String, nullable=False)  # "Gloss"
    sort_order        = Column(Integer, default=0)
    status            = Column(Integer, default=1)

    option = relationship("ProductOption", back_populates="attributes")

    __table_args__ = (UniqueConstraint("product_option_id", "title", name="uq_option_attribute_title"),)
```

Add to `Product` model:
```python
options = relationship("ProductOption", back_populates="product", cascade="all, delete-orphan")
```

---

## 3. Ingest Payload Shape

Ingest endpoint: `POST /api/ingest/{supplier_id}/products`

Each product in payload may include `options` array:
```json
{
  "supplier_sku": "DECAL-131",
  "product_name": "Decals - General Performance",
  "options": [
    {
      "option_key": "inkFinish",
      "title": "Ink Finish",
      "options_type": "Radio Button",
      "sort_order": 3,
      "master_option_id": 112,
      "ops_option_id": 456,
      "required": false,
      "attributes": [
        {"title": "Gloss",  "sort_order": 0, "ops_attribute_id": null},
        {"title": "Matte",  "sort_order": 1, "ops_attribute_id": null},
        {"title": "FLX+",   "sort_order": 2, "ops_attribute_id": null}
      ]
    }
  ]
}
```

`options` is optional — absent or empty means skip options upsert for that product (leave existing rows).

OPS may return `attributes` as a JSON string scalar. Ingest normalizes: if `attributes` is a string → `json.loads()`; if list → use directly; if null/missing → `[]`.

---

## 4. Ingest Logic

File: `backend/modules/catalog/ingest.py`

After product upsert, for each option in `options[]`:
1. Upsert `ProductOption` on `(product_id, option_key)` — update title, options_type, sort_order, master_option_id, ops_option_id, required, status
2. Delete all `ProductOptionAttribute` rows for that `product_option_id`
3. Bulk-insert fresh attributes from payload

Delete + re-insert (not upsert) for attributes: attribute titles can change between syncs; re-insert is simpler and safe since attributes have no downstream FKs yet.

---

## 5. Pydantic Schemas

File: `backend/modules/catalog/schemas.py`

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

Extend `ProductRead`:
```python
options: list[ProductOptionRead] = []
```

---

## 6. Route Change

File: `backend/modules/catalog/routes.py` — `get_product` endpoint

Add eager load:
```python
.options(
    selectinload(Product.options).selectinload(ProductOption.attributes)
)
```

---

## 7. Frontend

File: `frontend/src/lib/types.ts` — extend `Product`:
```typescript
export interface ProductOptionAttribute {
  id: string;
  title: string;
  sort_order: number;
}

export interface ProductOption {
  id: string;
  option_key: string;
  title: string;
  options_type: string | null;
  sort_order: number;
  master_option_id: number | null;
  required: boolean;
  attributes: ProductOptionAttribute[];
}

// In Product interface:
options: ProductOption[];
```

File: `frontend/src/app/storefront/vg/product/[product_id]/` — PDP

Add read-only options section below variants:
```
[Option Group: Ink Finish]    Gloss · Matte · FLX+
[Option Group: Material]      Arlon - 510 MT
[Option Group: Cut Type]      Through Cut · Kiss Cut · No Cutting
```

Render only options with `attributes.length > 0`. Sort by `sort_order`.

---

## 8. Error Handling

| Condition | Action |
|---|---|
| `options` key absent from payload | Skip options upsert; leave existing rows |
| `attributes` is JSON string | `json.loads()` in ingest; on parse error → `[]` |
| Unknown `options_type` | Store raw string; render as-is in UI |
| `product_additional_option_id` missing from OPS response | Store `ops_option_id = null`; upsert still works via `(product_id, option_key)` |

---

## 9. Testing

File: `backend/tests/test_catalog_ingest.py`

```python
@pytest.mark.asyncio
async def test_ingest_products_creates_options(client, db, seed_supplier):
    payload = [{
        "supplier_sku": "OPT-1",
        "product_name": "Opt Test",
        "options": [
            {
                "option_key": "inkFinish",
                "title": "Ink Finish",
                "options_type": "Radio Button",
                "sort_order": 0,
                "master_option_id": 112,
                "required": False,
                "attributes": [
                    {"title": "Gloss", "sort_order": 0},
                    {"title": "Matte", "sort_order": 1},
                ]
            }
        ]
    }]
    r = await client.post(f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=payload)
    assert r.status_code == 200

    prod = (await db.execute(select(Product).where(Product.supplier_sku == "OPT-1"))).scalar_one()
    opts = (await db.execute(select(ProductOption).where(ProductOption.product_id == prod.id))).scalars().all()
    assert len(opts) == 1
    assert opts[0].option_key == "inkFinish"
    assert opts[0].master_option_id == 112

    attrs = (await db.execute(
        select(ProductOptionAttribute).where(ProductOptionAttribute.product_option_id == opts[0].id)
    )).scalars().all()
    assert {a.title for a in attrs} == {"Gloss", "Matte"}


@pytest.mark.asyncio
async def test_ingest_products_options_idempotent(client, db, seed_supplier):
    base = {"supplier_sku": "OPT-2", "product_name": "Opt Idem", "options": [
        {"option_key": "cutting", "title": "Cutting", "options_type": "Radio Button",
         "sort_order": 0, "required": False,
         "attributes": [{"title": "Yes", "sort_order": 0}, {"title": "No", "sort_order": 1}]}
    ]}
    await client.post(f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=[base])

    # Second ingest — attribute list changes (add "Maybe")
    base["options"][0]["attributes"].append({"title": "Maybe", "sort_order": 2})
    r = await client.post(f"/api/ingest/{seed_supplier.id}/products", headers=SECRET, json=[base])
    assert r.status_code == 200

    prod = (await db.execute(select(Product).where(Product.supplier_sku == "OPT-2"))).scalar_one()
    opt = (await db.execute(select(ProductOption).where(ProductOption.product_id == prod.id))).scalar_one()
    attrs = (await db.execute(
        select(ProductOptionAttribute).where(ProductOptionAttribute.product_option_id == opt.id)
    )).scalars().all()
    assert len(attrs) == 3
    assert {a.title for a in attrs} == {"Yes", "No", "Maybe"}
```

---

## 10. File Summary

| File | Change |
|---|---|
| `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` | Add 4 fields to `productAdditionalOptionsFields` |
| `backend/modules/catalog/models.py` | Add `ProductOption`, `ProductOptionAttribute`; extend `Product.options` relationship |
| `backend/modules/catalog/schemas.py` | Add `ProductOptionRead`, `ProductOptionAttributeRead`; extend `ProductRead` |
| `backend/modules/catalog/routes.py` | Add `selectinload` for options + attributes in `get_product` |
| `backend/modules/catalog/ingest.py` | Parse + upsert options per product |
| `backend/tests/test_catalog_ingest.py` | 2 new option ingest tests |
| `frontend/src/lib/types.ts` | Add `ProductOption`, `ProductOptionAttribute`; extend `Product` |
| `frontend/src/app/storefront/vg/product/[product_id]/page.tsx` | Render options section |

---

## 11. Success Criteria

- `getManyDetailed` in n8n returns `title`, `master_option_id`, `attributes` per option
- `POST /api/ingest/.../products` with options payload → rows in `product_options` + `product_option_attributes`
- `GET /api/products/{id}` returns `options[]` with attributes
- PDP shows option groups + values for VG products
- Re-ingest with changed attributes → DB reflects new attribute set (no duplicates)
- Both new tests pass; full backend suite green
