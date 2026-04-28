# Task 16 — Field Mapping Page

## What This Task Built

Two frontend pages that let you define how a supplier's raw field names map to the canonical schema used across API-HUB.

- `/mappings` — A supplier picker. Lists all suppliers in the database, each with a "Configure Mappings" button.
- `/mappings/[supplierId]` — The mapping editor. Two columns: left side you type the supplier's raw field name, right side shows the canonical target field (fixed). A live JSON preview panel updates as you type.

### Files Created

| File | Purpose |
|------|---------|
| `frontend/src/app/mappings/page.tsx` | Supplier picker index page |
| `frontend/src/app/mappings/[supplierId]/page.tsx` | Field mapping editor with JSON preview |

### Canonical Fields (always the right column)

| Field | What it represents |
|-------|--------------------|
| `product_name` | Display name of the product |
| `supplier_sku` | Supplier's own product code |
| `brand` | Brand name |
| `description` | Long product description |
| `product_type` | Category (e.g. "apparel") |
| `color` | Variant color |
| `size` | Variant size |
| `base_price` | Wholesale price before markup |
| `inventory` | Stock count |
| `image_url` | Product image URL |
| `warehouse` | Which warehouse the variant is in |

---

## API Endpoints Used

| Method | Path | Used by |
|--------|------|---------|
| `GET` | `/api/suppliers` | Supplier picker — loads the list of suppliers |
| `GET` | `/api/suppliers/{id}` | Mapping editor — loads supplier name for the header |
| `PUT` | `/api/suppliers/{id}/mappings` | Save button — **not yet implemented in backend** |

---

## How to Test

### Prerequisites

Backend running on port 8001 and frontend on port 3002 (or 3000):

```bash
# Terminal 1 — Backend
cd "$(git rev-parse --show-toplevel)/backend" && source .venv/bin/activate
uvicorn main:app --reload --port 8001

# Terminal 2 — Frontend (install first if node_modules missing)
cd "$(git rev-parse --show-toplevel)/frontend"
npm install   # only needed once
npm run dev -- --port 3002
```

Make sure `.env.local` has:

```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

Seed data must be present (suppliers in DB):

```bash
cd "$(git rev-parse --show-toplevel)/backend" && source .venv/bin/activate
python3 seed_demo.py
```

---

### Test 1 — Supplier Picker Page Loads

**URL:** `http://localhost:3002/mappings`

**What to check:**
- Page loads with title "Field Mappings"
- All 3 seeded suppliers appear: SanMar, S&S Activewear, 4Over
- Each card shows the supplier name, slug, protocol, and PromoStandards code
- Each card has a "Configure Mappings" button

**curl check (HTTP status only — client-side data loads in browser):**

```bash
curl -s -o /dev/null -w "%{http_code}" http://localhost:3002/mappings
```

Expected: `200`

---

### Test 2 — Navigate to Mapping Editor

**What to do:**
1. Open `http://localhost:3002/mappings` in the browser
2. Click "Configure Mappings" on any supplier (e.g. SanMar)

**Expected:**
- URL changes to `/mappings/{supplier-uuid}`
- Header shows: `SanMar — map supplier fields to canonical schema`
- Table with 11 rows appears — one per canonical field
- Column headers: `Source (Supplier)` and `Target (Canonical)`
- All source inputs are empty
- Right column shows all 11 canonical field names in blue monospace
- JSON preview panel on the right shows: `// Add mappings to preview JSON`

**curl check (direct URL with real supplier ID):**

```bash
# Get a supplier ID first
curl -s http://localhost:8001/api/suppliers | python3 -c \
  "import sys,json; s=json.load(sys.stdin); print(s[0]['id'], s[0]['name'])"

# Then test the page
curl -s -o /dev/null -w "%{http_code}" \
  http://localhost:3002/mappings/{supplier-id}
```

Expected: `200`

---

### Test 3 — Live JSON Preview Updates

**What to do (in browser):**
1. Open the mapping editor for any supplier
2. In the row next to `product_name`, type `productTitle` in the source input

**Expected immediately (no save needed):**
- JSON preview panel updates to:

```json
{
  "productTitle": "product_name"
}
```

3. Add another mapping — next to `base_price` type `wholesalePrice`

**Expected JSON preview:**

```json
{
  "productTitle": "product_name",
  "wholesalePrice": "base_price"
}
```

4. Clear a field (delete the text)

**Expected:** That entry disappears from the JSON preview instantly.

---

### Test 4 — Save Button (Backend Not Yet Implemented)

**What to do:**
1. Enter at least one mapping
2. Click "Save Mappings"

**Expected (V0 — backend endpoint not built yet):**
- Error message appears in red: `API 404: ...` or similar
- Page does NOT crash
- Mappings you typed are still visible

**Note:** The `PUT /api/suppliers/{id}/mappings` endpoint does not exist yet in the backend. This is expected for Task 16. The save will work once Task 21 or a dedicated mappings endpoint is added.

---

## Test Results (2026-04-15)

| Test | Result |
|------|--------|
| GET /mappings — page returns 200 | ✅ PASS |
| GET /mappings/[supplierId] — page returns 200 | ✅ PASS |
| Supplier list loads from `/api/suppliers` (client-side) | ✅ PASS (verified via API directly) |
| Supplier name loads in editor header | ✅ PASS (verified via API directly) |
| Live JSON preview updates as you type | manual browser test required |
| Save button shows error gracefully (no backend endpoint) | manual browser test required |
