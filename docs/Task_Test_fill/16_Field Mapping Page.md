# Task 16 — Field Mapping Page

A "field mapping" in API-HUB defines how supplier-specific field names translate to the canonical schema that the rest of the platform uses. This task creates two frontend pages: a supplier picker that lists all suppliers, and a visual editor that lets you define how each supplier field maps to a canonical target field, with a live JSON preview.

Last updated: 2026-04-15

---

## Files Created

| File | Purpose |
|------|---------|
| `frontend/src/app/mappings/page.tsx` | Supplier picker — lists all suppliers with a "Configure Mappings" link for each |
| `frontend/src/app/mappings/[supplierId]/page.tsx` | Field mapping editor — two-column editor with live JSON preview |

---

## Why This Task Exists

Every PromoStandards supplier names their fields differently. SanMar might call a field `productTitle`, while S&S Activewear calls the same thing `itemName`. When n8n pulls data from a supplier, it needs to know how to translate those supplier-specific names into the canonical schema that the rest of API-HUB understands (`product_name`, `brand`, `base_price`, etc.).

The field mapping page answers:
- What is the supplier's raw field name for "product name"?
- What is the supplier's raw field name for "base price"?
- How do all the supplier fields map to the canonical fields the system expects?

Without this, n8n would have to hard-code field names per supplier — which breaks every time a supplier changes their API.

---

## Canonical Fields

The right column (target) is always fixed — these are the fields the system expects:

| Canonical Field | What it represents |
|-----------------|-------------------|
| `product_name` | The display name of the product |
| `supplier_sku` | The supplier's own product code |
| `brand` | Brand name (e.g. "Port & Company") |
| `description` | Long product description |
| `product_type` | Category of product (e.g. "apparel") |
| `color` | Variant color |
| `size` | Variant size |
| `base_price` | Wholesale price before markup |
| `inventory` | Stock count |
| `image_url` | URL to the product image |
| `warehouse` | Which warehouse the variant is in |

---

## Pages

### `/mappings` — Supplier Picker

**File:** `frontend/src/app/mappings/page.tsx`

Fetches all suppliers from `GET /api/suppliers` and displays them as cards. Each card shows:
- Supplier name
- Slug, protocol, and PromoStandards code (in monospace)
- A "Configure Mappings" button that links to `/mappings/[supplier-id]`

This is the entry point for the Field Mapping section — the sidebar "Field Mapping" link goes here.

---

### `/mappings/[supplierId]` — Mapping Editor

**File:** `frontend/src/app/mappings/[supplierId]/page.tsx`

Two-column layout:

**Left column — Mapping Editor table:**
- One row per canonical field (11 rows total)
- Left cell: a text input where you type the supplier's raw field name
- Right cell: the canonical target field name (read-only, shown in blue monospace)
- Header row labels: "Source (Supplier)" and "Target (Canonical)"

**Right column — JSON Preview:**
- Updates live as you fill in source fields
- Only shows rows where a source field has been entered
- Format: `{ "supplier_field_name": "canonical_field_name" }`
- Shows placeholder comment `// Add mappings to preview JSON` when nothing is mapped yet

**Save button:**
- Calls `PUT /api/suppliers/{supplierId}/mappings` with the mapping as JSON body
- Shows "Saved ✓" in green on success
- Shows the error message in red if the API call fails (backend endpoint not yet implemented)

---

## How It Connects to the Rest of the System

```
suppliers table (Task 3)
       │
       └── Field Mapping Page (Task 16)
             Reads: GET /api/suppliers  →  supplier list
             Reads: GET /api/suppliers/{id}  →  supplier name in header
             Writes: PUT /api/suppliers/{id}/mappings  →  save mapping config
```

**n8n workflow (Task 21)** will read these mappings when pulling data from a supplier so it knows which supplier field to read for each canonical field.

> **Note:** The `PUT /api/suppliers/{id}/mappings` backend endpoint is not yet implemented. The save button will show an error until that endpoint exists. The UI works fully for viewing and editing mappings.

---

## How to Test

Make sure the frontend dev server is running:

```bash
cd "$(git rev-parse --show-toplevel)/frontend"
npm run dev
```

Make sure the backend is running (so suppliers load):

```bash
cd "$(git rev-parse --show-toplevel)/backend" && source .venv/bin/activate
uvicorn main:app --reload --port 8001
```

Make sure `.env.local` has the correct API URL:

```
NEXT_PUBLIC_API_URL=http://localhost:8001
```

**Open the supplier picker:**

Navigate to `http://localhost:3000/mappings`

Expected: a list of suppliers (SanMar, S&S Activewear, 4Over) each with a "Configure Mappings" button.

**Open the mapping editor:**

Click "Configure Mappings" on any supplier, or navigate directly to:

```
http://localhost:3000/mappings/<supplier-uuid>
```

Expected: two-column editor with 11 rows (one per canonical field) and an empty JSON preview.

**Type a mapping:**

In the "Source (Supplier)" input next to `product_name`, type `productTitle`.

Expected: the JSON preview updates immediately to:

```json
{
  "productTitle": "product_name"
}
```

**Fill in more fields and check the preview grows.**

**Click "Save Mappings":**

- If the backend endpoint exists: shows "Saved ✓" in green
- If not yet implemented: shows the API error in red — this is expected for V0
