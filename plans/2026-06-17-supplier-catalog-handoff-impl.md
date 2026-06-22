# Supplier Catalog Handoff (api-hub → graphx) — Implementation Plan

> ⚠️ **SUPERSEDED 2026-06-22 → see `2026-06-22-connect-manage-catalog-ingest.md`.**
> Targeted graphx-platform-web (Supabase), now retired as the downstream in favor of
> **GraphX-Manage** (Prisma/PG18, active). Do NOT execute this against graphx-platform-web.
> Kept for history; the new plan re-targets the same design to GraphX-Manage.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax. **This plan spans TWO repos** — do Phase A+B in graphx, Phase C in api-hub, Phase D across both.

**Goal:** Push normalized supplier products from api-hub (GraphX Connect) into graphx's Universal Catalog under the VG tenant, as `IMPORTED_FROM_SUPPLIER`, with Color/Size bound as shared master options.

**Architecture:** graphx gains a `ProductSupplierSource` identity model + `IMPORTED_FROM_SUPPLIER` genesis + a shared-secret `POST /api/ingest/supplier-products` endpoint (pattern-copied from the existing ops-sync route). api-hub gains an outbound exporter that serializes a product (reusing the `/export` query) and POSTs the contract. Master options are bound, never created per-product.

**Tech Stack:** graphx — Next.js (App Router route handlers), Prisma 6, Supabase Postgres, pnpm. api-hub — FastAPI, async SQLAlchemy, httpx, pytest.

**Design doc:** `/Users/tanishq/.claude/plans/cached-growing-planet.md`

---

## File structure

**graphx** (`/Users/tanishq/Documents/project-files/graphx-platform-web`):
- Modify `packages/catalog-db/prisma/schema.prisma` — add enum value + `ProductSupplierSource` model.
- New migration `packages/catalog-db/prisma/migrations/<ts>_supplier_source/migration.sql`.
- New `apps/admin/src/app/api/ingest/supplier-products/route.ts` (template: `apps/admin/src/app/api/ops-sync/products/route.ts`).
- New test `apps/admin/src/app/api/ingest/supplier-products/route.test.ts` (or repo's test convention).

**api-hub** (`/Users/tanishq/Documents/project-files/api-hub/api-hub/backend`):
- New `modules/catalog/exporter.py`.
- Modify `modules/catalog/routes.py` — refactor `export_product` (:196) into a reusable builder that INCLUDES options; add push routes.
- New `tests/test_supplier_export.py`.

Reuse: ops-sync route (auth + upsert blocks), `export_product` query (:203–211), `httpx.AsyncClient` pattern (`modules/rest_connector/client.py`), VG tenant `slug="vg"`, `derive_options` from `feat/variant-option-collapse`.

---

## Phase A — graphx schema

### Task A1: Add `IMPORTED_FROM_SUPPLIER` + `ProductSupplierSource`

**Files:** Modify `packages/catalog-db/prisma/schema.prisma`; create migration.

- [ ] **Step 1: Edit the enum.** In `enum GenesisSource { ... }` (schema.prisma ~:80) add a line:
```prisma
  IMPORTED_FROM_SUPPLIER /// pushed in from a wholesale supplier via GraphX Connect (api-hub)
```

- [ ] **Step 2: Add the model.** Append:
```prisma
model ProductSupplierSource {
  id           String   @id @default(cuid())
  product_id   String
  product      Product  @relation(fields: [product_id], references: [id], onDelete: Cascade)
  supplier_key String   /// api-hub Supplier.slug, e.g. "sanmar"
  supplier_sku String   /// api-hub Product.supplier_sku, e.g. "PC54"
  raw_payload  Json?
  created_at   DateTime @default(now())
  updated_at   DateTime @updatedAt

  @@unique([supplier_key, supplier_sku])
  @@index([product_id])
}
```
Add the back-relation on `model Product`: `supplier_sources ProductSupplierSource[]`.
(Natural key is `(supplier_key, supplier_sku)` — globally unique because supplier SKUs are; the product it points to already carries `tenant_id`.)

- [ ] **Step 3: Validate.**
Run: `cd packages/catalog-db && CATALOG_DATABASE_URL="postgresql://u:p@localhost:5432/db" npx prisma@6 validate`
Expected: `The schema ... is valid 🚀`

- [ ] **Step 4: Generate the migration** (match repo convention — hand-authored SQL under `prisma/migrations/`, RLS + search_path pinned like #40–#52). Create `migration.sql`:
```sql
-- add enum value (must be its own statement, cannot run inside a txn block with use)
ALTER TYPE "GenesisSource" ADD VALUE IF NOT EXISTS 'IMPORTED_FROM_SUPPLIER';

CREATE TABLE IF NOT EXISTS "ProductSupplierSource" (
  "id" TEXT PRIMARY KEY,
  "product_id" TEXT NOT NULL REFERENCES "Product"("id") ON DELETE CASCADE,
  "supplier_key" TEXT NOT NULL,
  "supplier_sku" TEXT NOT NULL,
  "raw_payload" JSONB,
  "created_at" TIMESTAMP(3) NOT NULL DEFAULT now(),
  "updated_at" TIMESTAMP(3) NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS "ProductSupplierSource_supplier_key_supplier_sku_key"
  ON "ProductSupplierSource"("supplier_key","supplier_sku");
CREATE INDEX IF NOT EXISTS "ProductSupplierSource_product_id_idx"
  ON "ProductSupplierSource"("product_id");

ALTER TABLE "ProductSupplierSource" ENABLE ROW LEVEL SECURITY;
-- deny-by-default + service-role bypass, matching migrations #40–#52
CREATE POLICY "pss_service_role_all" ON "ProductSupplierSource"
  AS PERMISSIVE FOR ALL TO service_role USING (true) WITH CHECK (true);
```
> Note: `ALTER TYPE ... ADD VALUE` cannot run inside a transaction with later use of the value — keep it in its own migration step / before the table that defaults to it. Here the table doesn't default to the enum, so order is safe.

- [ ] **Step 5: Commit.**
```bash
git add packages/catalog-db/prisma/schema.prisma packages/catalog-db/prisma/migrations
git commit -m "feat(catalog-db): IMPORTED_FROM_SUPPLIER genesis + ProductSupplierSource"
```

---

## Phase B — graphx ingest endpoint

### Task B1: Route skeleton + auth + tenant resolve (TDD)

**Files:** Create `apps/admin/src/app/api/ingest/supplier-products/route.ts` + test.

- [ ] **Step 1: Write the failing test** (`route.test.ts`, mirror repo test setup):
```ts
import { POST } from "./route";
function req(body: unknown, secret?: string) {
  return new Request("http://t/api/ingest/supplier-products", {
    method: "POST", headers: secret ? { "x-ingest-secret": secret } : {},
    body: JSON.stringify(body),
  });
}
test("401 on wrong secret", async () => {
  process.env.INGEST_SUPPLIER_SECRET = "s3cret";
  const r = await POST(req({ tenant_slug: "vg", products: [] }, "wrong"));
  expect(r.status).toBe(401);
});
test("404 unknown tenant", async () => {
  process.env.INGEST_SUPPLIER_SECRET = "s3cret";
  const r = await POST(req({ tenant_slug: "nope", products: [] }, "s3cret"));
  expect(r.status).toBe(404);
});
```
- [ ] **Step 2: Run, expect fail** (`pnpm --filter @graphx/admin test route.test`). Module missing.
- [ ] **Step 3: Implement skeleton** — copy the auth + tenant-resolve from `api/ops-sync/products/route.ts:164–197`, swapping the secret env to `INGEST_SUPPLIER_SECRET` and header to `x-ingest-secret`. Define the contract types:
```ts
type SupplierProduct = {
  supplier_sku: string; name: string; brand?: string|null; description?: string|null;
  product_type?: string|null; category?: string|null;
  images?: { url: string; type?: string; color?: string|null }[];
  options?: { option_key: "color"|"size"; title: string; attributes: { title: string }[] }[];
  variants?: { color?: string|null; size?: string|null; sku?: string|null;
    prices?: { price_type: string; quantity_min: number; quantity_max?: number|null; price: number }[] }[];
};
type Payload = { supplier_key: string; tenant_slug: string; products: SupplierProduct[] };
```
Validate `payload.supplier_key && payload.tenant_slug && Array.isArray(payload.products)` → 400 otherwise.
- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** `feat(admin): supplier-products ingest endpoint — auth + tenant`.

### Task B2: Upsert product via ProductSupplierSource + sizes

- [ ] **Step 1: Test** — POST one product with the secret → expect `200`, report `{created:1}`, and a `Product` with `genesis_source=IMPORTED_FROM_SUPPLIER`, `internal_name="sup:sanmar:PC54"`, `tenant_id=vg.id`; a `ProductSupplierSource(sanmar,PC54)` row; sizes upserted. Re-POST → `{updated:1}`, no duplicate.
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement** the per-product loop:
```ts
for (const p of payload.products) {
  const internal = `sup:${payload.supplier_key}:${p.supplier_sku}`;
  const src = await prisma.productSupplierSource.findUnique({
    where: { supplier_key_supplier_sku: { supplier_key: payload.supplier_key, supplier_sku: p.supplier_sku } },
    select: { product_id: true },
  });
  const data: Prisma.ProductUncheckedCreateInput = {
    tenant_id: tenant.id, scope: Scope.TENANT_NATIVE,
    internal_name: internal, name: p.name,
    long_description: p.description ?? null,
    product_type: p.product_type === "apparel" ? "15" : (p.product_type ?? "15"),
    sync_state: SyncState.PENDING,
    genesis_source: GenesisSource.IMPORTED_FROM_SUPPLIER, genesis_at: new Date(),
  };
  let productId: string;
  if (src) { const d = {...data}; delete (d as any).genesis_source; delete (d as any).genesis_at;
    await prisma.product.update({ where: { id: src.product_id }, data: d }); productId = src.product_id; }
  else { const c = await prisma.product.create({ data }); productId = c.id;
    await prisma.productSupplierSource.create({ data: {
      product_id: productId, supplier_key: payload.supplier_key, supplier_sku: p.supplier_sku, raw_payload: p as any } }); }
  // sizes: distinct from variants
  const sizeTitles = [...new Set((p.variants ?? []).map(v => v.size).filter(Boolean) as string[])];
  for (const name of sizeTitles) {
    await prisma.productSize.upsert({
      where: { product_id_name: { product_id: productId, name } },
      create: { product_id: productId, name, width: 0, height: 0, unit: "INCH", sort_order: 10 },
      update: {} });
  }
}
```
(Carries `raw_payload` for provenance; pricing carried there, not as sell price — see design.)
- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** `feat(admin): supplier ingest — product upsert + sizes via ProductSupplierSource`.

### Task B3: Bind Color/Size MASTER options (not per-product)

- [ ] **Step 1: Test** — POST a product with `options:[{color:[Red,Navy]},{size:[S,M]}]` → exactly **two** `MasterOption` rows exist total (`option_key` `color`,`size`) regardless of how many products; the product has two `ProductOptionBinding`s; binding attributes match the values.
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement** find-or-create master option once, then bind:
```ts
async function ensureMasterOption(option_key: string, title: string) {
  const found = await prisma.masterOption.findFirst({ where: { option_key, scope: Scope.UNIVERSAL } });
  if (found) return found;
  return prisma.masterOption.create({ data: { option_key, title, scope: Scope.UNIVERSAL,
    internal_name: `master-${option_key}`, status: "1" } });
}
// inside the product loop, after productId:
for (const opt of p.options ?? []) {
  const mo = await ensureMasterOption(opt.option_key, opt.title);
  const binding = await prisma.productOptionBinding.upsert({
    where: { product_id_master_option_id: { product_id: productId, master_option_id: mo.id } },
    create: { product_id: productId, master_option_id: mo.id, attributes_subset: [] },
    update: {} });
  for (const a of opt.attributes) {
    await prisma.productOptionBindingAttribute.upsert({
      where: { /* repo's unique — e.g. binding_id_attribute_key */ product_option_binding_id_attribute_key:
        { product_option_binding_id: binding.id, attribute_key: a.title.toLowerCase() } },
      create: { product_option_binding_id: binding.id, master_option_attribute_id: null,
        attribute_key: a.title.toLowerCase(), label: a.title },
      update: { label: a.title } });
  }
}
```
> Verify the exact `ProductOptionBindingAttribute` unique key + required fields against schema.prisma during impl (ops-sync route keys on `ops_attribute_id`; the supplier path has none, so use `(binding_id, attribute_key)` — add that `@@unique` if absent, in Task A1's migration).
- [ ] **Step 4: Run, expect pass.** Assert the two-master-options invariant.
- [ ] **Step 5: Commit** `feat(admin): supplier ingest — bind shared Color/Size master options`.

---

## Phase C — api-hub exporter

### Task C1: Reusable payload builder (incl options)

**Files:** Modify `modules/catalog/routes.py`; create `modules/catalog/exporter.py`; test `tests/test_supplier_export.py`.

- [ ] **Step 1: Test** (`test_supplier_export.py`, use `db`/`seed_supplier` fixtures + the `_mk_product` helper pattern from `test_option_collapse.py`):
```python
@pytest.mark.asyncio
async def test_build_supplier_payload(db, seed_supplier):
    from modules.catalog.exporter import build_supplier_product
    # create product + variants + derived options (call derive_options)
    from modules.catalog.option_collapse import derive_options
    p = await _mk_product(db, seed_supplier, [("Red","S"),("Navy","M")])
    await derive_options(db, p.id)
    out = await build_supplier_product(db, p.id)
    assert out["supplier_sku"] == "PC54"
    keys = {o["option_key"] for o in out["options"]}
    assert keys == {"color","size"}
    assert any(v["color"]=="Red" for v in out["variants"])
```
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement** `build_supplier_product(db, product_id) -> dict` in `exporter.py` — reuse the `export_product` query (routes.py:203–211) but **include options** (the current `/export` omits them):
```python
async def build_supplier_product(db, product_id):
    res = await db.execute(select(Product).where(Product.id==product_id).options(
        selectinload(Product.variants).selectinload(ProductVariant.prices),
        selectinload(Product.images), selectinload(Product.sizes),
        selectinload(Product.options).selectinload(ProductOption.attributes)))
    p = res.scalar_one_or_none()
    if not p: raise HTTPException(404, "Product not found")
    return {
        "supplier_sku": p.supplier_sku, "name": p.product_name, "brand": p.brand,
        "description": p.description, "product_type": p.product_type, "category": p.category,
        "images": [{"url": i.url, "type": i.image_type, "color": i.color} for i in (p.images or [])],
        "options": [{"option_key": o.option_key, "title": o.title,
            "attributes": [{"title": a.title} for a in (o.attributes or [])]} for o in (p.options or [])],
        "variants": [{"color": v.color, "size": v.size, "sku": v.sku,
            "prices": [{"price_type": pr.price_type, "quantity_min": pr.quantity_min,
                "quantity_max": pr.quantity_max, "price": float(pr.price)} for pr in (v.prices or [])]}
            for v in (p.variants or [])],
    }
```
- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** `feat(catalog): build_supplier_product payload (incl options)`.

### Task C2: Pusher (httpx) + skip-no-options guard

- [ ] **Step 1: Test** — mock `httpx.AsyncClient.post`; `push_products_to_graphx(db, supplier_id=seed.id)` posts an envelope `{supplier_key, tenant_slug:"vg", products:[...]}` to `GRAPHX_INGEST_URL` with header `x-ingest-secret`; products with no options are skipped + counted.
- [ ] **Step 2: Run, expect fail.**
- [ ] **Step 3: Implement** in `exporter.py` (config via `os.environ`, httpx pattern from `rest_connector/client.py`):
```python
async def push_products_to_graphx(db, supplier_id=None, tenant_slug="vg", batch=50):
    url = os.environ["GRAPHX_INGEST_URL"]; secret = os.environ["GRAPHX_INGEST_SECRET"]
    sup = await db.get(Supplier, supplier_id)
    q = select(Product.id).where(Product.archived_at.is_(None))
    if supplier_id: q = q.where(Product.supplier_id == supplier_id)
    ids = (await db.execute(q)).scalars().all()
    sent=skipped=0; results=[]
    buf=[]
    for pid in ids:
        prod = await build_supplier_product(db, pid)
        if not prod["options"]:  # needs derive_options first
            skipped+=1; continue
        buf.append(prod)
        if len(buf)>=batch:
            results.append(await _post(url, secret, sup.slug, tenant_slug, buf)); sent+=len(buf); buf=[]
    if buf: results.append(await _post(url, secret, sup.slug, tenant_slug, buf)); sent+=len(buf)
    return {"sent": sent, "skipped": skipped, "batches": results}

async def _post(url, secret, supplier_key, tenant_slug, products):
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(url, headers={"x-ingest-secret": secret},
            json={"supplier_key": supplier_key, "tenant_slug": tenant_slug, "products": products})
        return {"status": r.status_code, "body": r.json() if r.headers.get("content-type","").startswith("application/json") else None}
```
- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** `feat(catalog): push_products_to_graphx exporter (batched, skip-no-options)`.

### Task C3: Trigger routes

- [ ] **Step 1: Test** (`client` fixture) — `POST /api/products/{id}/push-to-graphx` (mock httpx) → 200 with a result dict; `POST /api/suppliers/{id}/push-to-graphx` → 200.
- [ ] **Step 2: Run, expect fail (404).**
- [ ] **Step 3: Implement** in `routes.py` — import the exporter; add the two routes using `CurrentUser` + `get_db`, calling `build_supplier_product`/`push_products_to_graphx`. Also fold options into the existing `GET /{id}/export` JSON (it currently omits them) by reusing `build_supplier_product`.
- [ ] **Step 4: Run, expect pass.**
- [ ] **Step 5: Commit** `feat(catalog): push-to-graphx trigger routes + options in /export`.

---

## Phase D — E2E (staging, manual)

- [ ] Set `GRAPHX_INGEST_URL` + `GRAPHX_INGEST_SECRET` (api-hub `.env`) and `INGEST_SUPPLIER_SECRET` (graphx env) to the same secret.
- [ ] Ingest one SanMar style in api-hub → run `derive_options` → `POST /api/suppliers/{id}/push-to-graphx`.
- [ ] In graphx: confirm the Product under `vg` with `genesis_source=IMPORTED_FROM_SUPPLIER`, `internal_name="sup:sanmar:<sku>"`, two `ProductOptionBinding`s, and exactly two `color`/`size` `MasterOption` rows total. Re-run → idempotent (updated, no dup).

---

## Self-review

- **Spec coverage:** schema (A1) · ingest endpoint auth/tenant (B1) · product+sizes upsert keyed on ProductSupplierSource (B2) · master-option binding (B3) · payload builder incl options (C1) · batched pusher + skip-no-options (C2) · trigger routes (C3) · E2E (D). All design sections mapped.
- **Placeholders:** two flagged "verify during impl" (exact `ProductOptionBindingAttribute` unique key; repo test harness) — explicit verification steps, not gaps. Resolve against schema.prisma in B3.
- **Type consistency:** `build_supplier_product` / `push_products_to_graphx` / contract field names (`supplier_key`, `supplier_sku`, `option_key`, `attributes[].title`) consistent across api-hub emit and graphx accept.
- **Dependency:** Phase C needs `derive_options` (`feat/variant-option-collapse`) merged — stated; pusher skips + logs option-less products.
