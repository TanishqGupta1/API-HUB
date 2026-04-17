# Sinchana — Sprint Tasks

**Total: 4 tasks** | Branch: `sinchana-sprint-v1`

---

## Task 0.3: Install shadcn/ui

**Priority:** Do this FIRST — blocks all other frontend work.
**Files:** `frontend/` (new `components/ui/` directory created)

### Steps

- [ ] **Step 1:** Navigate to frontend directory
```bash
cd api-hub/frontend
```

- [ ] **Step 2:** Initialize shadcn
```bash
npx shadcn@latest init -d
```
This creates `components/ui/` and configures Tailwind for shadcn.

- [ ] **Step 3:** Install required components
```bash
npx shadcn@latest add button card input table badge separator scroll-area
```

- [ ] **Step 4:** Verify components installed
```bash
ls src/components/ui/
# Expected: button.tsx  card.tsx  input.tsx  table.tsx  badge.tsx  separator.tsx  scroll-area.tsx
```

- [ ] **Step 5:** Verify the app still builds
```bash
npm run build
# Expected: no errors
```

- [ ] **Step 6:** Commit
```bash
git add -A
git commit -m "feat: install shadcn/ui components — button, card, input, table, badge, separator, scroll-area"
```

---

## Task 20: Terminology + Loading States + Sidebar Rename

**Priority:** After Task 0.3
**Files to modify:**
- `frontend/src/app/layout.tsx` OR `frontend/src/components/Sidebar.tsx` — sidebar navigation labels
- `frontend/src/app/page.tsx` — dashboard text
- `frontend/src/app/products/page.tsx` — page title and loading text
- `frontend/src/app/products/[id]/page.tsx` — button labels and badges
- `frontend/src/app/suppliers/page.tsx` — loading text
- `frontend/src/app/sync/page.tsx` — job type labels
- `frontend/src/app/markup/page.tsx` — page title (if exists)
- `frontend/src/app/mappings/page.tsx` — page title

### What to change

**Find and replace these strings across ALL frontend files:**

| Find (current) | Replace with | Files |
|----------------|-------------|-------|
| `"Vendors"` | `"Suppliers"` | `page.tsx` (dashboard) |
| `"Technical Index"` | `"Product Catalog"` | `products/page.tsx` |
| `"Customers"` (in sidebar/nav only) | `"Storefronts"` | sidebar component |
| `"Push to OPS"` | `"Publish to Store"` | `products/[id]/page.tsx` |
| `"Sync Jobs"` (in sidebar/nav) | `"Data Updates"` | sidebar component |
| `"Markup Rules"` (in sidebar/nav) | `"Pricing Rules"` | sidebar component |
| `"Field Mapping"` or `"Field Mappings"` (in sidebar) | `"Data Configuration"` | sidebar component |
| `"_QUERYING_INDEX..."` | `"Loading products..."` | `products/page.tsx` |
| `"_QUERYING_ENDPOINT_REGISTRY..."` | `"Connecting..."` | `suppliers/page.tsx` |
| `"_FETCHING_METRICS..."` | `"Loading dashboard..."` | `page.tsx` (dashboard) |
| `"Auth_Error"` | `"Connection Failed"` | any badge/status display |
| `"delta"` (in sync job type display) | `"Recent Changes"` | `sync/page.tsx` |
| `"full_sync"` or `"full"` (in sync job type) | `"Full Refresh"` | `sync/page.tsx` |
| `"inventory_sync_v2"` | `"Inventory Update"` | `page.tsx` (dashboard) |
| `"delta_product_ingest"` | `"Product Sync"` | `page.tsx` (dashboard) |

**Sidebar section renames:**
- `"Orchestration"` → `"Products"`
- `"Management"` → `"Configuration"`
- `"Catalog"` → `"Product Catalog"`
- Remove duplicate "Add Supplier" from the Actions section (keep the one on the suppliers page)

**Empty states — add to pages that show empty tables:**

In `products/page.tsx`, when product list is empty:
```tsx
<p>No products yet. Connect a supplier to start syncing products.</p>
```

In `sync/page.tsx`, when sync jobs is empty:
```tsx
<p>No sync history yet. Activate a supplier to see data updates here.</p>
```

In `markup/page.tsx` (if exists), when no rules:
```tsx
<p>No pricing rules set. Add a rule to control storefront pricing.</p>
```

### Steps

- [ ] **Step 1:** Open the sidebar component (`layout.tsx` or `Sidebar.tsx`). Rename all section labels and nav items per the table above.

- [ ] **Step 2:** Open each page file. Find and replace loading state text, badge labels, and page titles.

- [ ] **Step 3:** Add empty state messages to pages that show lists/tables.

- [ ] **Step 4:** Run the frontend and check every page visually
```bash
cd frontend && npm run dev
# Open http://localhost:3000
# Click through: Dashboard, Product Catalog, Suppliers, Storefronts, Pricing Rules, Data Updates, Data Configuration
# Verify: ZERO instances of SOAP, WSDL, HMAC, delta, _QUERYING, Auth_Error visible
```

- [ ] **Step 5:** Commit
```bash
git add -A
git commit -m "feat: rename all technical jargon to business language across frontend"
```

---

## Task 21: Simplified Add Supplier Form (3 steps)

**Priority:** After Task 20
**Files to modify:**
- `frontend/src/components/suppliers/reveal-form.tsx` — complete rewrite
- `frontend/src/app/suppliers/page.tsx` — may need updates

### Current form (5 steps — too complex)
1. Choose protocol (PromoStandards / REST / HMAC)
2. Select supplier from grid OR enter custom name + URL
3. Enter credentials (ID + password)
4. Test connection (shows "11 active services")
5. Set sync schedule (4 dropdowns)

### New form (3 steps — business language)

**Step 1: "Choose your supplier"**
- Search bar at top: placeholder `"Search 994+ suppliers..."`
- Grid of popular suppliers: SanMar, S&S Activewear, Alphabroder, 4Over (show name + code as badge)
- Clicking a PS supplier auto-sets `protocol: "promostandards"` and `promostandards_code`
- Link at bottom: "Can't find yours? Add a custom supplier"
- **Custom supplier path:** show 3 fields:
  - "Supplier Name" (text input)
  - "API Address" (text input, placeholder: `"https://api.example.com"`)
  - "API Type" (dropdown): `"Standard API"` | `"Secure API (signed requests)"`
  - Help text under dropdown: "Not sure? Choose 'Standard API' — your supplier's documentation will tell you if signed requests are needed."
  - "Standard API" maps to `protocol: "rest"`, "Secure API" maps to `protocol: "rest_hmac"`

**Step 2: "Connect your account"**
- Two fields:
  - "API Username" (text input, placeholder: `"Your API username"`)
  - "API Password" (password input)
- Help text: "Your supplier provides these when you sign up for API access. Contact [supplier name] support if you don't have them."
- "Test Connection" button
- Success state: green check + "Connected to [SanMar] — ready to sync"
- Failure state: red X + "Could not connect. Please check your username and password." + "Try Again" button

**Step 3: "Activate"**
- Summary card: supplier name, connection status
- Single dropdown: "How often should we check for updates?"
  - Options: `"Recommended (automatic)"` | `"Every 30 minutes"` | `"Every hour"` | `"Once a day"`
  - Default: "Recommended (automatic)"
- "Activate Supplier" button → loading state → "Supplier Activated!" → redirect to supplier list

**Backend mapping for schedule dropdown:**
- "Recommended" → `{inv: "30min", price: "daily", prod: "daily", img: "weekly"}`
- "Every 30 minutes" → `{inv: "30min", price: "30min", prod: "daily", img: "weekly"}`
- "Every hour" → `{inv: "1hour", price: "1hour", prod: "daily", img: "weekly"}`
- "Once a day" → `{inv: "daily", price: "daily", prod: "daily", img: "weekly"}`

### Steps

- [ ] **Step 1:** Read the current `reveal-form.tsx` to understand the existing state management and API calls.

- [ ] **Step 2:** Rewrite the component with the 3-step flow. Keep the same API calls (`POST /api/suppliers`, `GET /api/ps-directory/companies`) but change the UI.

- [ ] **Step 3:** Test with the frontend dev server — add a PromoStandards supplier (SanMar) and a custom supplier.

- [ ] **Step 4:** Commit
```bash
git add -A
git commit -m "feat: simplify Add Supplier form from 5 steps to 3 — remove jargon, add help text"
```

---

## Task 2: PromoStandards Response Schemas

**Priority:** After V0 tasks (0.3, 20, 21) are done. Can start in parallel with Urvashi's Task 1 and Vidhi's Task 3.
**Files to create:**
- `backend/modules/promostandards/__init__.py` (empty)
- `backend/modules/promostandards/schemas.py`

### What this is

Pydantic models that represent SOAP XML responses from PromoStandards suppliers. These are **NOT database models** — they're intermediate typed containers. The SOAP client (Task 3) outputs these. The normalizer (Task 4) reads these and writes to the DB.

### Steps

- [ ] **Step 1:** Create the module directory
```bash
mkdir -p backend/modules/promostandards
touch backend/modules/promostandards/__init__.py
```

- [ ] **Step 2:** Create `backend/modules/promostandards/schemas.py`:

```python
"""Pydantic models for deserialized PromoStandards SOAP responses.

These are NOT database models. They are typed containers for parsed XML,
giving the normalizer clean input regardless of which supplier the data came from.
"""

from pydantic import BaseModel


class PSProductPart(BaseModel):
    """A single color/size variant from getProduct response.

    SanMar calls these 'parts' — one 'PC61 Essential Tee' product has
    parts like 'Navy/M', 'Navy/L', 'White/S'.
    """
    part_id: str
    color_name: str | None = None
    size_name: str | None = None
    description: str | None = None


class PSProductData(BaseModel):
    """A product from getProduct or getProductSellable response."""
    product_id: str
    product_name: str | None = None
    description: str | None = None
    brand: str | None = None
    categories: list[str] = []
    product_type: str = "apparel"
    primary_image_url: str | None = None
    parts: list[PSProductPart] = []


class PSInventoryLevel(BaseModel):
    """Inventory for one part from getInventoryLevels response.

    quantity_available is capped at 500 per PromoStandards convention.
    """
    product_id: str
    part_id: str
    quantity_available: int = 0
    warehouse_code: str | None = None


class PSPricePoint(BaseModel):
    """Price for one part from PPC (Pricing & Configuration) service."""
    product_id: str
    part_id: str
    price: float
    quantity_min: int = 1
    quantity_max: int | None = None
    price_type: str = "piece"  # piece, dozen, case


class PSMediaItem(BaseModel):
    """An image/media asset from Media Content service."""
    product_id: str
    url: str
    media_type: str = "front"  # front, back, side, swatch, detail
    color_name: str | None = None
```

- [ ] **Step 3:** Verify the module imports correctly
```bash
cd backend && source .venv/bin/activate
python -c "from modules.promostandards.schemas import PSProductData, PSProductPart, PSInventoryLevel, PSPricePoint, PSMediaItem; print('All schemas imported OK')"
```

- [ ] **Step 4:** Commit
```bash
git add backend/modules/promostandards/
git commit -m "feat: PromoStandards response Pydantic schemas — PSProductData, PSInventoryLevel, PSPricePoint, PSMediaItem"
```
