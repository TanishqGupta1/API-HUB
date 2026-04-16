# Vidhi — Sprint Tasks

**Total: 3 tasks** | Branch: `vidhi-sprint-v1`

---

## Task 0.4: Customers Page (Storefronts)

**Priority:** Start immediately (after Sinchana's Task 0.3 shadcn install is merged)
**File:** `frontend/src/app/customers/page.tsx`
**Backend API:** `GET /api/customers`, `POST /api/customers`, `DELETE /api/customers/{id}` — all already exist

### What this page shows

A list of OnPrintShop storefronts. Each row: name, OPS base URL, active status. An "Add Storefront" button opens an inline form with OAuth2 credential fields.

**Note:** In the V1f UX overhaul (Task 20), "Customers" will be renamed to "Storefronts" in the sidebar. For now, build the page at `/customers` — the rename happens separately.

### Steps

- [ ] **Step 1:** Create `frontend/src/app/customers/page.tsx` with:

**Table columns:**
- Store Name
- OPS URL (show just the hostname, e.g., "acme.onprintshop.com")
- Status (Active/Inactive badge)
- Products Pushed (count, from API if available, or "—")
- Actions (Deactivate / Delete buttons)

**Add Storefront form fields:**
- "Store Name" — text input, placeholder: "e.g., Acme Corp Store"
- "OPS GraphQL URL" — text input, placeholder: "e.g., https://acme.onprintshop.com/graphql"
- "OAuth Token URL" — text input, placeholder: "e.g., https://acme.onprintshop.com/oauth/token"
- "Client ID" — text input
- "Client Secret" — password input (write-only, never shown back)
- Help text: "You can find these credentials in your OnPrintShop admin panel under Settings > API."

**API calls:**
```typescript
// Load customers
const customers = await api<Customer[]>("/api/customers");

// Create customer
await api("/api/customers", {
  method: "POST",
  body: JSON.stringify({
    name: formData.name,
    ops_base_url: formData.opsBaseUrl,
    ops_token_url: formData.opsTokenUrl,
    ops_client_id: formData.opsClientId,
    ops_client_secret: formData.opsClientSecret,
  }),
});

// Delete customer
await api(`/api/customers/${id}`, { method: "DELETE" });
```

**Empty state:** "No storefronts added. Add your OnPrintShop storefront to start publishing products."

- [ ] **Step 2:** Test with backend running:
```bash
# Terminal 1: backend
cd backend && source .venv/bin/activate && uvicorn main:app --reload --port 8000

# Terminal 2: frontend
cd frontend && npm run dev
```
Open http://localhost:3000/customers — add a test customer, verify it appears in the list, verify delete works.

- [ ] **Step 3:** Commit
```bash
git add frontend/src/app/customers/
git commit -m "feat: Customers (Storefronts) page — list + add form with OAuth2 credentials"
```

---

## Task 0.5: Workflows Page (Pipeline Visualizer)

**Priority:** After Task 0.4
**Files:**
- `frontend/src/app/workflows/page.tsx`
- `frontend/src/components/workflows/pipeline-view.tsx`

### What this page shows

An animated pipeline diagram showing the data flow: Supplier → Fetch → Normalize → Store → Publish to Store. Each node has a status indicator (idle/running/done/error). Links to the n8n editor.

This is **mostly static for V0** — it becomes live when n8n workflows are deployed in V1e.

### Steps

- [ ] **Step 1:** Create `frontend/src/components/workflows/pipeline-view.tsx`:

A horizontal row of 5 connected nodes:

```
[Supplier] → [Fetch Data] → [Normalize] → [Store in DB] → [Publish to Store]
```

Each node is a card with:
- Icon (use emoji or lucide-react icons)
- Label
- Status badge: "Idle" (gray), "Running" (blue pulse), "Done" (green), "Error" (red)
- Animated connecting lines between nodes (use CSS animation from globals.css `drawLine` keyframe)

Default state: all nodes "Idle" with gray badges.

- [ ] **Step 2:** Create `frontend/src/app/workflows/page.tsx`:

Page layout:
- Title: "Data Pipeline"
- Subtitle: "How products flow from suppliers to your storefronts"
- The `PipelineView` component
- Below the pipeline: "Open n8n Editor" button linking to `http://localhost:5678` (or configurable URL)
- Info panel: "Sync schedules are managed in n8n. The pipeline runs automatically once activated."

- [ ] **Step 3:** Test:
```bash
cd frontend && npm run dev
```
Open http://localhost:3000/workflows — verify the pipeline diagram renders with all 5 nodes connected.

- [ ] **Step 4:** Commit
```bash
git add frontend/src/app/workflows/ frontend/src/components/workflows/
git commit -m "feat: Workflows page with pipeline visualizer — 5-node animated diagram"
```

---

## Task 3: WSDL Resolver

**Priority:** After V0 tasks. Can run in parallel with Sinchana's Task 2 and Urvashi's Task 1.
**File to create:** `backend/modules/promostandards/resolver.py`

**Prerequisite:** Sinchana must have created the `backend/modules/promostandards/` directory and `__init__.py` in her Task 2. If she hasn't yet, create the directory yourself:
```bash
mkdir -p backend/modules/promostandards
touch backend/modules/promostandards/__init__.py
```

### What this does

The PromoStandards directory API returns endpoint data for each supplier. Each endpoint has a `ServiceType` like "Product Data", "Inventory Levels", etc. But different suppliers register with inconsistent names ("Product Data" vs "ProductData", "Inventory" vs "Inventory Levels"). This resolver normalizes those strings and finds the right WSDL URL.

### Steps

- [ ] **Step 1:** Create `backend/modules/promostandards/resolver.py`:

```python
"""Resolve WSDL URLs from cached PromoStandards directory endpoints."""

# PS directory returns ServiceType as strings like "Product Data", "Inventory",
# "Product Pricing and Configuration", "Media Content". Suppliers register
# with inconsistent naming. This resolver normalizes for matching.

_SERVICE_TYPE_ALIASES = {
    "product data": "product_data",
    "productdata": "product_data",
    "product": "product_data",
    "inventory": "inventory",
    "inventory levels": "inventory",
    "inventorylevels": "inventory",
    "product pricing and configuration": "ppc",
    "ppc": "ppc",
    "pricing": "ppc",
    "pricing and configuration": "ppc",
    "media content": "media",
    "mediacontent": "media",
    "media": "media",
}


def _normalize_service_type(raw: str) -> str:
    """Normalize a PS ServiceType string to a canonical key."""
    return _SERVICE_TYPE_ALIASES.get(raw.strip().lower(), raw.strip().lower())


def resolve_wsdl_url(endpoint_cache: list[dict], service_type: str) -> str | None:
    """Find the ProductionURL for a given service type in the cached endpoints.

    Args:
        endpoint_cache: List of endpoint dicts from PS directory API.
            Each dict has keys like ServiceType, ProductionURL, TestURL, Version, Name.
        service_type: One of "product_data", "inventory", "ppc", "media".

    Returns:
        The ProductionURL string, or None if not found.

    Example:
        >>> endpoints = [{"ServiceType": "Product Data", "ProductionURL": "https://ws.sanmar.com/...?wsdl"}]
        >>> resolve_wsdl_url(endpoints, "product_data")
        'https://ws.sanmar.com/...?wsdl'
    """
    target = _normalize_service_type(service_type)
    for ep in endpoint_cache or []:
        # Try both ServiceType and Name fields — suppliers use different keys
        raw_type = ep.get("ServiceType") or ep.get("Name") or ""
        if _normalize_service_type(raw_type) == target:
            url = ep.get("ProductionURL")
            if url:
                return url
    return None
```

- [ ] **Step 2:** Verify it works:
```bash
cd backend && source .venv/bin/activate
python -c "
from modules.promostandards.resolver import resolve_wsdl_url

# Test with sample endpoint data (like what PS directory returns)
endpoints = [
    {'ServiceType': 'Product Data', 'ProductionURL': 'https://ws.sanmar.com/productdata?wsdl', 'Version': '2.0.0'},
    {'ServiceType': 'Inventory Levels', 'ProductionURL': 'https://ws.sanmar.com/inventory?wsdl', 'Version': '2.0.0'},
    {'ServiceType': 'Product Pricing and Configuration', 'ProductionURL': 'https://ws.sanmar.com/ppc?wsdl', 'Version': '1.0.0'},
    {'ServiceType': 'Media Content', 'ProductionURL': 'https://ws.sanmar.com/media?wsdl', 'Version': '1.0.0'},
]

assert resolve_wsdl_url(endpoints, 'product_data') == 'https://ws.sanmar.com/productdata?wsdl'
assert resolve_wsdl_url(endpoints, 'inventory') == 'https://ws.sanmar.com/inventory?wsdl'
assert resolve_wsdl_url(endpoints, 'ppc') == 'https://ws.sanmar.com/ppc?wsdl'
assert resolve_wsdl_url(endpoints, 'media') == 'https://ws.sanmar.com/media?wsdl'

# Test with inconsistent naming (some suppliers use different strings)
assert resolve_wsdl_url([{'ServiceType': 'ProductData', 'ProductionURL': 'http://x'}], 'product_data') == 'http://x'
assert resolve_wsdl_url([{'Name': 'Inventory', 'ProductionURL': 'http://y'}], 'inventory') == 'http://y'

# Test missing
assert resolve_wsdl_url(endpoints, 'nonexistent') is None
assert resolve_wsdl_url([], 'product_data') is None
assert resolve_wsdl_url(None, 'product_data') is None

print('All resolver tests passed!')
"
```

- [ ] **Step 3:** Commit
```bash
git add backend/modules/promostandards/resolver.py
git commit -m "feat: WSDL resolver — maps PS ServiceType strings to ProductionURL with alias normalization"
```
