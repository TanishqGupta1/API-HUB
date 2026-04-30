# Multi-Supplier Polymorphic Product Model — Design Spec

**Date:** 2026-04-29  
**Status:** Locked  
**Author:** Session design — approved by Tanishq

---

## 1. Problem

API-HUB must ingest products from structurally different supplier types:

| Supplier type | Example | Product shape |
|---|---|---|
| **OPS print** (VG OPS) | Decals, Business Cards | No variants. W×H configurator. ~35 options with `multiplier`/`setup_cost`. Formula pricing: `base × area × Σmultipliers + Σsetup_cost`. |
| **PS apparel** (SanMar, S&S) | T-shirts, Polos | Pre-computed variants (color × size). Tiered pricing bands (MSRP/Net/Sale/Case). Live inventory per variant. |
| **PS hard goods** (4Over) | Banners, Signage | Similar to print but sourced via PromoStandards REST, not OPS GraphQL. |

A single flat `products` table cannot efficiently model all three. But separate tables per supplier violates CLAUDE.md ("never create per-supplier code").

---

## 2. Decision: Polymorphic detail tables (Option B)

**Architecture:** Shared `products` spine + type-specific 1:1 detail tables.

```
products (spine — all types)
├── apparel_details   1:1  (product_type = "apparel")
├── print_details     1:1  (product_type = "print")
├── product_variants  1:N  (apparel only — color × size)
├── variant_prices    1:N  (apparel only — tiered pricing per variant)
├── product_sizes     1:N  (print only — pre-set W×H options)
├── product_images    1:N  (all types)
└── product_options   1:N  (print primarily, occasionally apparel)
    └── product_option_attributes  1:N
```

**Rationale:**
- Apparel and print are structurally different enough that merging their type-specific fields into one table creates null-heavy rows and confusing queries.
- Type-specific detail tables keep each product type's schema clean while sharing the common spine (name, SKU, category, images, options).
- Does NOT require per-supplier code — `product_type` is a VARCHAR discriminator, not a foreign key to a supplier-specific table.

---

## 3. Data model

### `products` (existing, extended)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| supplier_id | UUID FK → suppliers.id | |
| supplier_sku | VARCHAR(255) | |
| product_name | VARCHAR(500) | |
| product_type | VARCHAR(50) | "apparel" \| "print" — validated at app layer |
| brand | VARCHAR(255) nullable | |
| category | VARCHAR(255) nullable | |
| category_id | UUID FK → categories.id nullable | |
| description | TEXT nullable | |
| image_url | TEXT nullable | |
| ops_product_id | VARCHAR(255) nullable | |
| external_catalogue | INTEGER nullable | |
| last_synced | TIMESTAMPTZ nullable | |
| archived_at | TIMESTAMPTZ nullable | |

### `apparel_details` (new)

| Column | Type | Notes |
|---|---|---|
| product_id | UUID PK, FK → products.id CASCADE | 1:1 |
| pricing_method | VARCHAR(50) | default "tiered_variant" |
| raw_payload | JSONB nullable | original supplier JSON |

### `print_details` (new)

| Column | Type | Notes |
|---|---|---|
| product_id | UUID PK, FK → products.id CASCADE | 1:1 |
| pricing_method | VARCHAR(50) | default "formula" |
| min_width | NUMERIC(10,2) nullable | |
| max_width | NUMERIC(10,2) nullable | |
| min_height | NUMERIC(10,2) nullable | |
| max_height | NUMERIC(10,2) nullable | |
| size_unit | VARCHAR(10) | default "in" |
| base_price_per_sq_unit | NUMERIC(10,4) nullable | |
| raw_payload | JSONB nullable | |

### `variant_prices` (new — apparel tiered pricing)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| variant_id | UUID FK → product_variants.id CASCADE, index | |
| price_type | VARCHAR(20) | MSRP \| Net \| Sale \| Case |
| quantity_min | INTEGER | |
| quantity_max | INTEGER nullable | null = open-ended top tier |
| price | NUMERIC(10,2) | |
| UNIQUE | (variant_id, price_type, quantity_min) | |

### `product_sizes` (new — print pre-set sizes)

| Column | Type | Notes |
|---|---|---|
| id | UUID PK | |
| product_id | UUID FK → products.id CASCADE, index | |
| width | NUMERIC(10,2) | |
| height | NUMERIC(10,2) | |
| unit | VARCHAR(10) | default "in" |
| label | VARCHAR(100) nullable | e.g. `4"x6"` |
| UNIQUE | (product_id, width, height) | |

### Supplier columns (added via schema upgrade)

```
adapter_class     VARCHAR(64) NULL   -- e.g. "OPSAdapter", "SanMarAdapter"
last_full_sync    TIMESTAMPTZ NULL
last_delta_sync   TIMESTAMPTZ NULL
```

### SyncJob columns (added via schema upgrade)

```
errors  JSONB NULL   -- [{sku, error}, ...] for per-product errors during import
```

---

## 4. Ingest contract — `ProductIngest` schema

All supplier adapters produce `ProductIngest` objects. Shape is supplier-agnostic.

```python
class ProductIngest(BaseModel):
    supplier_sku: str
    product_name: str
    product_type: str = "apparel"          # "apparel" | "print"
    brand: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    ops_product_id: Optional[str] = None
    external_catalogue: Optional[int] = None
    category_external_id: Optional[str] = None
    category_name: Optional[str] = None
    variants: list[VariantIngest] = []
    images: list[ImageIngest] = []
    options: list[OptionIngest] = []
    sizes: list[ProductSizeIngest] = []    # new — print products
    price_tiers: list[PriceTierIngest] = []  # new — apparel tiered pricing
    print_details: Optional[PrintDetailsIngest] = None  # new
    apparel_details: Optional[ApparelDetailsIngest] = None  # new

    @model_validator(mode="after")
    def _validate_type_details(self):
        if self.product_type == "print" and self.print_details is None:
            raise ValueError("print products require print_details")
        if self.product_type == "apparel" and self.apparel_details is None:
            self.apparel_details = ApparelDetailsIngest()  # auto-default
        return self
```

**Validation rule:** Enforced at app layer only. No DB CHECK constraint.

---

## 5. `persist_product` service

`backend/modules/catalog/persistence.py`

```python
async def persist_product(
    supplier_id: UUID,
    item: ProductIngest,
    db: AsyncSession,
    now: datetime,
    category_id: UUID | None = None,
) -> UUID:
    """Upsert one product. Returns product UUID. Caller commits."""
    # 1. Upsert products spine
    product_id = await _upsert_spine(supplier_id, item, db, now, category_id)
    # 2. Route by product_type
    if item.product_type == "print":
        await _persist_print_path(product_id, item, db)
    elif item.product_type == "apparel":
        await _persist_apparel_path(product_id, item, db)
    return product_id
```

**Error handling:** `persist_product` raises on unexpected errors. Callers (ingest endpoint, adapter orchestrator) decide whether to abort or collect-and-continue.

---

## 6. Supplier adapter pipeline

### 6.1 Adapter interface (`modules/import_jobs/base.py`)

```python
class BaseAdapter(ABC):
    @abstractmethod
    async def discover(self, mode: DiscoveryMode, limit: int | None) -> list[ProductRef]: ...
    
    @abstractmethod
    async def hydrate_product(self, ref: ProductRef) -> ProductIngest: ...
```

### 6.2 Adapter registry (`modules/import_jobs/registry.py`)

```python
ADAPTERS: dict[str, type[BaseAdapter]] = {}

def register(adapter_class_name: str):
    def decorator(cls):
        ADAPTERS[adapter_class_name] = cls
        return cls
    return decorator

def get_adapter(supplier: Supplier, db: AsyncSession) -> BaseAdapter:
    cls = ADAPTERS.get(supplier.adapter_class)
    if not cls:
        raise ValueError(f"No adapter registered for {supplier.adapter_class!r}")
    return cls(supplier, db)
```

### 6.3 Adapter implementations (Phase 2+)

| Adapter class | `suppliers.adapter_class` value | Plan |
|---|---|---|
| `OPSAdapter` | `"OPSAdapter"` | Phase 2 |
| `SanMarAdapter` | `"SanMarAdapter"` | Phase 3 |
| `SSAdapter` | `"SSAdapter"` | Phase 3 |

### 6.4 OPS adapter field mapping

OPS GraphQL `product` → `ProductIngest`:

| OPS field | ProductIngest field |
|---|---|
| `product_id` | `ops_product_id`, `supplier_sku` = `"OPS-{product_id}"` |
| `product_name` | `product_name` |
| `catalogue_id` | `external_catalogue` |
| `options[].option_key` | `options[].option_key` |
| `options[].attributes[].multiplier` | `options[].attributes[].multiplier` |
| `options[].attributes[].setup_cost` | `options[].attributes[].setup_cost` |
| always | `product_type = "print"` |
| dimensions from options | `print_details.min_width`, `max_width`, etc. |

### 6.5 SanMar/PromoStandards field mapping

PS GetProduct `PSProduct` → `ProductIngest`:

| PS field | ProductIngest field |
|---|---|
| `productId` | `supplier_sku` |
| `productName` | `product_name` |
| `partId` (per part) | `variants[].part_id` |
| `colorName` | `variants[].color` |
| `labelSize` | `variants[].size` |
| GetPricing tiers | `price_tiers[]` |
| GetInventory levels | `variants[].inventory` |
| always | `product_type = "apparel"` |

### 6.6 Adapter class column

`suppliers.adapter_class` VARCHAR(64) — set when creating the supplier DB row. The adapter registry reads it to instantiate the correct adapter. No code paths branch on supplier name or slug.

---

## 7. Discovery modes

| Mode | When used | How |
|---|---|---|
| `first_n` | Initial import (15–20 products for testing) | Fetch first N product refs from list endpoint |
| `explicit_list` | Re-import specific SKUs | Caller provides list of `supplier_sku` |
| `full` | Weekly reconciliation | Fetch all product refs from supplier |
| `delta` | Daily sync | Fetch only products changed since `last_delta_sync` |
| `closeouts` | Archival sweep | Fetch discontinued SKUs, set `archived_at` |

---

## 8. Error handling

| Error type | Behavior |
|---|---|
| Auth error (401/403 from supplier) | Fatal — abort job immediately, status = "failed" |
| Per-product API error | Collect `{sku, error}` in `sync_jobs.errors`, continue loop |
| Per-product persist error | Collect in `sync_jobs.errors`, continue loop |
| All products fail | Job status = "failed" |
| Some products fail | Job status = "partial_success" |
| All products succeed | Job status = "completed" |

---

## 9. Pricing model

### Print (formula-based)

```
price = base_price_per_sq_unit × width × height × Πmultipliers + Σsetup_costs
```

Where multipliers and setup_costs come from the user's selected option attributes.

### Apparel (tiered variant)

Price looked up from `variant_prices` by `(variant_id, price_type, quantity_min ≤ qty ≤ quantity_max)`.

Markup is applied on top by `modules/markup/` (existing, unchanged in Phase 1).

---

## 10. Rollout phases

| Phase | Deliverable | Depends on |
|---|---|---|
| **Phase 1** | Polymorphic model + `persist_product` + ingest refactor | — |
| **Phase 2** | OPS inbound adapter — reads live VG OPS products | Phase 1 |
| **Phase 3** | SanMar/PromoStandards adapter — apparel ingest | Phase 1 |
| **Phase 4** | Pricing API — `/api/pricing/quote` for both types | Phase 1 |
| **Phase 5** | Frontend PDP — polymorphic product detail panel | Phase 4 |

---

## 11. Locked decisions

| Decision | Choice | Reason |
|---|---|---|
| Type discriminator | VARCHAR, not PG ENUM | CLAUDE.md constraint |
| Detail-table presence enforcement | App layer only (persist_product + tests) | No cross-table DB CHECK possible |
| Tiered pricing storage | `variant_prices` table (not JSON blob) | Queryable; markup engine reads it |
| Dimensions storage | `product_sizes` (pre-set W×H) + `print_details` (min/max bounds) | Configurator needs both |
| `_upsert_options` location | `persistence.py` (not ingest.py) | Shared by all adapters |
| Adapter registry key | `suppliers.adapter_class` VARCHAR column | No per-supplier code in routes |
| Import trigger | Manual `POST /api/suppliers/{id}/import` + BackgroundTasks | UI button → polling |
| SanMar credentials | Live tests blocked until creds received | Fixture-only in Phase 3 |
