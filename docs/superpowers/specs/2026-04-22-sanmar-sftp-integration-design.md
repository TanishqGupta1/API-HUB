# SanMar SFTP Integration — Design Spec

**Date:** 2026-04-22  
**Author:** Tanishq  
**Status:** Approved — ready for implementation planning

---

## Context

SanMar API credentials received from Christian. SanMar delivers bulk catalog data via SFTP (not PromoStandards SOAP). An n8n workflow skeleton (`n8n-workflows/sanmar-sftp-pull.json`) already exists but has a placeholder CSV column mapping and no real credentials wired in.

**SFTP details:**
```
Host:     ftp.sanmar.com
Port:     2200
Protocol: SFTP
```
Username + password to be stored in n8n credential `sanmar-sftp-creds` (never in code or `.env`).

---

## What Already Works

| Component | Status |
|---|---|
| n8n workflow skeleton (`sanmar-sftp-pull.json`) | ✅ Exists — SFTP list → download → parse CSV → shape → POST ingest |
| `POST /api/ingest/{supplier_id}/products` | ✅ Live — `X-Ingest-Secret` auth, batch upsert |
| `POST /api/ingest/{supplier_id}/inventory` | ✅ Live |
| `POST /api/ingest/{supplier_id}/pricing` | ✅ Live |
| Batch loop (500 rows per POST) | ✅ In workflow |

---

## What's Missing

| Gap | Impact |
|---|---|
| No real SFTP credentials in n8n | Workflow can't connect |
| CSV column mapping is guesses | Shape Products node will produce empty/wrong data |
| `*.csv` filter may grab unintended files | Risk of feeding pricing CSV into products endpoint |
| `INGEST_SHARED_SECRET` not set in n8n env | Every POST returns 401 |
| No SanMar supplier row in DB | `Resolve SanMar SID` code node throws — no supplier with `slug: "sanmar"` |
| No error branch | Silent failure — bad batch kills run with no log |

---

## Architecture

```
n8n (SFTP workflow)                     FastAPI
┌─────────────────────────────┐        ┌──────────────────────────────────┐
│ Manual / Cron Trigger       │        │ POST /api/ingest/{sid}/products  │
│ → Resolve SanMar SID        │        │   → normalize → upsert Product   │
│ → SFTP: List Files          │───────▶│   → upsert ProductVariant        │
│ → Filter: product file only │        │   → upsert ProductImage          │
│ → SFTP: Download            │        │                                  │
│ → Parse CSV                 │        │ POST /api/ingest/{sid}/inventory │
│ → Shape Products (mapping)  │───────▶│   → update Variant.inventory     │
│ → Loop 500 rows             │        │                                  │
│ → POST /api/ingest          │        │ POST /api/ingest/{sid}/pricing   │
│ → Error branch → log        │───────▶│   → update Variant.base_price    │
└─────────────────────────────┘        └──────────────────────────────────┘
```

One workflow handles all file types. A Code node after the file listing routes each file to the correct ingest endpoint based on filename.

---

## Tasks

### Phase 1 — Prerequisites (unblock everything)

#### Task P1: Create SanMar supplier row in DB

**Who:** Tanishq (one curl, 2 minutes)

```bash
curl -X POST http://localhost:8000/api/suppliers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "SanMar",
    "slug": "sanmar",
    "protocol": "sftp",
    "auth_config": {}
  }'
```

Save the returned `id` — needed for every other step.

**Acceptance:** `GET /api/suppliers` returns a SanMar row with `slug: "sanmar"`.

---

#### Task P2: Create `sanmar-sftp-creds` credential in n8n

**Who:** Tanishq (in n8n UI — credentials never committed to code)

In n8n UI → Credentials → New → SFTP:
- Name: `SanMar SFTP`
- Host: `ftp.sanmar.com`
- Port: `2200`
- Username: `[from Christian]`
- Password: `[from Christian]`

The workflow references this credential by name — no workflow JSON changes needed.

**Acceptance:** Credential saves without error. (Connection test via n8n.)

---

#### Task P3: Set `INGEST_SHARED_SECRET` in n8n environment

**Who:** Tanishq

In n8n: Settings → Environment Variables → add:
```
INGEST_SHARED_SECRET = <value from api-hub/.env>
```

The workflow already reads `$env.INGEST_SHARED_SECRET` and sends it as `X-Ingest-Secret` header.

**Acceptance:** `curl -H "X-Ingest-Secret: <value>" http://localhost:8000/api/ingest/<sid>/products` returns 200 (not 401).

---

### Phase 2 — Discovery (one-time, reveals actual file structure)

#### Task D1: Run directory listing to discover FTP files

**Who:** Tanishq

Import a throwaway n8n workflow with 2 nodes:
1. Manual trigger
2. SFTP: List Files (path `/`, no filter, credential: `SanMar SFTP`)

Execute. Capture the full file list. Document:
- Exact filenames (products file, pricing file, inventory file if separate)
- Whether subdirectories exist
- File sizes (estimate row counts)

**Deliverable:** File list pasted into this doc's appendix (update inline).

---

#### Task D2: Download one product file and inspect column headers

**Who:** Tanishq

Download the product CSV from FTP (via n8n SFTP node or command line SFTP client). Open in Excel/Numbers. Document the exact column names for:

| Data Point | Guessed Column Name | Actual Column Name |
|---|---|---|
| Style / product SKU | `STYLE` | TBD |
| Product name | `PRODUCT_NAME` | TBD |
| Brand | `BRAND_NAME` | TBD |
| Description | `PRODUCT_DESCRIPTION` | TBD |
| Color name | `COLOR_NAME` | TBD |
| Size name | `SIZE_NAME` | TBD |
| Variant SKU | `UNIQUE_KEY` | TBD |
| Piece price | `PIECE_PRICE` | TBD |
| Inventory qty | `QTY` | TBD |
| Warehouse | `WAREHOUSE` | TBD |
| Image URL | `PRODUCT_IMAGE` | TBD |

**Deliverable:** Fill in the "Actual Column Name" column above. This directly feeds Task W1.

---

### Phase 3 — Workflow Completion

#### Task W1: Fix Shape Products column mapping

**File:** `n8n-workflows/sanmar-sftp-pull.json` — `Shape Products` node (`code-002`)

Replace the `// MAPPING PLACEHOLDER` block with real column names from Task D2. Pattern:

```js
return rows.map((item) => {
  const p = item.json;
  return {
    json: {
      supplier_sku: String(p.<ACTUAL_STYLE_COL> || ''),
      product_name: p.<ACTUAL_NAME_COL> || 'Unnamed',
      brand: p.<ACTUAL_BRAND_COL> || 'SanMar',
      description: p.<ACTUAL_DESC_COL> || null,
      product_type: 'apparel',
      image_url: p.<ACTUAL_IMAGE_COL> || null,
      variants: [{
        sku: String(p.<ACTUAL_SKU_COL> || ''),
        color: p.<ACTUAL_COLOR_COL> || null,
        size: p.<ACTUAL_SIZE_COL> || null,
        base_price: parseFloat(p.<ACTUAL_PRICE_COL> || 0),
        inventory: parseInt(p.<ACTUAL_QTY_COL> || 0),
        warehouse: p.<ACTUAL_WH_COL> || null,
      }],
      images: p.<ACTUAL_IMAGE_COL>
        ? [{ url: p.<ACTUAL_IMAGE_COL>, image_type: 'front', sort_order: 0 }]
        : [],
      options: []
    }
  };
});
```

**Acceptance:** Shape Products node output has `supplier_sku`, `product_name`, `variants[0].base_price` populated for every row.

---

#### Task W2: Fix SFTP file filter — product file only

**File:** `n8n-workflows/sanmar-sftp-pull.json` — `SFTP: List Files` node (`sftp-001`)

Change the filter from `*.csv` to the exact product filename discovered in Task D1. Example: if the file is `SanMar_All_Products.csv`, set filter to `SanMar_All_Products.csv`.

This prevents the inventory or pricing CSV from being fed into the products endpoint.

---

#### Task W3: Add file-type router for pricing + inventory

**File:** `n8n-workflows/sanmar-sftp-pull.json`

After `SFTP: List Files`, add a Code node that categorizes each file:

```js
const files = $input.all().map(i => i.json);
return files.map(f => ({
  json: {
    ...f,
    file_type: f.name.toLowerCase().includes('price') ? 'pricing'
             : f.name.toLowerCase().includes('invent') ? 'inventory'
             : 'products'
  }
}));
```

Then use a Switch node to route:
- `file_type == "products"` → existing download → shape → `POST /api/ingest/{sid}/products`
- `file_type == "pricing"` → download → shape pricing → `POST /api/ingest/{sid}/pricing`
- `file_type == "inventory"` → download → shape inventory → `POST /api/ingest/{sid}/inventory`

If SanMar only provides one combined file (discovered in D1), skip this task.

---

#### Task W4: Add error handling branch

**File:** `n8n-workflows/sanmar-sftp-pull.json`

Add an error output connection from the `POST /ingest/products` HTTP node. On failure:
```
Error branch → Code node (format error message) → POST /api/push-log (status: "failed", error: <message>)
```

Or simpler: connect error output to a Set node that formats `{ status: "failed", error: $json.message }` then to an HTTP node posting to a `/api/sync-jobs/{job_id}` status update endpoint.

---

### Phase 4 — E2E Verification

#### Task E1: Run full workflow, verify in DB

**Who:** Tanishq (manual)

```bash
# 1. Import updated workflow
docker cp n8n-workflows/sanmar-sftp-pull.json api-hub-n8n-1:/tmp/sanmar-sftp-pull.json
docker exec api-hub-n8n-1 n8n import:workflow --input=/tmp/sanmar-sftp-pull.json

# 2. Execute in n8n UI — watch each node

# 3. Verify products
curl "http://localhost:8000/api/products?supplier_id=<sanmar_id>&limit=5" | python3 -m json.tool

# 4. Verify variants
curl "http://localhost:8000/api/products/<product_id>" | python3 -m json.tool
```

**Acceptance:**
- Products show `supplier_sku` matching SanMar style numbers
- Variants have `color`, `size`, `base_price` populated
- Images have URLs
- No 500 errors in FastAPI logs

---

#### Task E2: Verify in storefront frontend

Open `http://localhost:3000/storefront/vg` — SanMar products visible with correct brand badges, images, pricing. Variant picker shows real colors and sizes.

---

## Team Assignment

| Task | Who | Effort | Order |
|---|---|---|---|
| P1 — Create SanMar DB row | **Tanishq** | XS | First — needs API access |
| P2 — n8n SFTP credential | **Tanishq** | XS | First — has the password |
| P3 — n8n env var | **Tanishq** | XS | First — knows .env value |
| D1 — FTP directory listing | **Vidhi** | S | After Tanishq does P2 |
| D2 — Inspect CSV columns | **Vidhi** | S | After D1 |
| W1 — Fix column mapping | **Vidhi** | S | After D2 |
| W2 — Fix file filter | **Vidhi** | XS | After D1 |
| W3 — File type router | **Vidhi** | M | After D1 (if needed) |
| W4 — Error handling branch | **Sinchana** | S | Any time — no blockers |
| E1 — E2E DB verify | **Tanishq** | M | After W1+W2 merged |
| E2 — Frontend verify | **Sinchana** | S | After E1 |

---

## Blockers

| Blocker | Status |
|---|---|
| SanMar SFTP username + password | **Have host/port. Need user/pass from Christian.** |
| Actual CSV column names | Unknown until D1+D2 discovery run |
| SanMar supplier row in DB | Not created yet (Task P1) |

---

## Out of Scope

- PromoStandards SOAP for SanMar (SFTP is the delivery method provided)
- Real-time inventory via REST API (FTP-only for now; revisit when SanMar provides REST creds)
- Image download + resize pipeline (image URLs from CSV fed directly to `image_url` field; processed by `ops_push/image_pipeline.py` at push time)
- Scheduled cron (manual trigger only until E2E passes; add cron trigger as next step after verification)
