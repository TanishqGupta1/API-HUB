# Task 1 — Remove Supplier Credentials From API Response

**Date:** 2026-05-15
**Author:** Vidhi
**Branch:** Vidhi
**Status:** Done locally, pending approval

---

## What type of task is this?

**Security fix — Backend + Frontend**

---

## What was the problem?

Every time the Suppliers page loaded, the backend was sending the supplier's username and password to the browser inside the API response.

Example of what the old API was returning:

```json
{
  "id": "abc-123",
  "name": "SanMar",
  "auth_config": {
    "id": "myusername",
    "password": "mysecretpassword",
    "customer_number": "12345678"
  }
}
```

The credentials are stored encrypted in the PostgreSQL database using Fernet (AES-128) encryption — which is correct and secure. But the moment the backend sent the API response, it decrypted them and included the plain text values. So any logged-in admin could open their browser's DevTools → Network tab → click the suppliers request → and read the password in plain text.

---

## How does this relate to the existing codebase?

The issue was in one specific file:

**`backend/modules/suppliers/schemas.py`** — The `SupplierRead` class defines what the backend sends back when anyone calls `GET /api/suppliers` or `GET /api/suppliers/{id}`. This class had a field called `auth_config: dict` which told the backend to include the full credentials dictionary in every response.

The database model (`backend/modules/suppliers/models.py`) stores `auth_config` as an `EncryptedJSON` column — encrypted at rest. But `SupplierRead` was reading from the decrypted in-memory object and passing it straight to the API response.

---

## Why was it necessary to fix?

- **Security rule:** APIs should never return passwords, API keys, or secrets in list or detail responses. This is a standard rule across all web applications.
- **The database encryption was being undone** at the response layer. Encrypting in the database but sending plain text over the network defeats the purpose.
- **Any session compromise** would expose supplier credentials — not just access to the admin UI.
- **The lead explicitly flagged this** as a problem that must be fixed.

---

## What changed and why

### Backend — `backend/modules/suppliers/schemas.py`

**Before:**
```python
class SupplierRead(BaseModel):
    ...
    auth_config: dict        # ← was sending the full credentials
    ...
```

**After:**
```python
class SupplierRead(BaseModel):
    ...
    has_credentials: bool = False   # ← only sends true/false
    ...
```

**Why this approach:** The frontend only needs to know whether credentials are configured — it does not need to display or edit the actual values. A simple boolean `has_credentials` gives the UI exactly what it needs without exposing the sensitive data.

---

### Backend — `backend/modules/suppliers/routes.py`

In every place that builds a `SupplierRead` response (4 places: list, get, create, patch), we added:

```python
data.has_credentials = bool(supplier.auth_config)
```

This reads `auth_config` from the database model (which is fine — the backend is allowed to read it), checks if it is non-empty, and sets `has_credentials` to `true` or `false`. The actual values never leave the server.

**The 4 places updated:**
- `list_suppliers` — GET /api/suppliers (list)
- `get_supplier` — GET /api/suppliers/{id}
- `create_supplier` — POST /api/suppliers
- `patch_supplier` — PATCH /api/suppliers/{id}

---

### Frontend — `frontend/src/lib/types.ts`

**Before:**
```typescript
export interface Supplier {
  auth_config: Record<string, string>;   // ← expected credentials from API
  ...
}
```

**After:**
```typescript
export interface Supplier {
  has_credentials: boolean;   // ← expects only the status flag
  ...
}
```

This keeps the TypeScript type in sync with what the API actually returns now.

---

### Frontend — `frontend/src/app/(admin)/suppliers/[id]/page.tsx`

**Before:** The supplier detail page had a section called "Authentication Credentials" that rendered editable input fields for each key in `auth_config`. Because the API no longer returns those values, those fields would be empty — which could confuse an admin into thinking credentials are not set when they actually are.

**After:** Replaced the editable fields with a clear status panel:

- If `has_credentials` is `true` → green panel with "Credentials configured" + shield icon
- If `has_credentials` is `false` → orange panel with "No credentials set"

Also fixed the save handler to exclude `has_credentials` from the PATCH payload (it is a read-only derived field, not something you update):

```typescript
// Before
const { id: _id, created_at, product_count, ...updateData } = supplier;

// After
const { id: _id, created_at, product_count, has_credentials: _hc, ...updateData } = supplier;
```

---

## What did NOT change

- How credentials are saved when adding a new supplier — that flow (`reveal-form.tsx`, `suppliers/new/page.tsx`) still sends `auth_config` in the POST body, which is correct. You are allowed to write credentials to the server; you just should not read them back.
- The database schema — `auth_config` is still stored encrypted in the `suppliers` table.
- The test connection flow — still works, still uses real credentials from the database internally.
- The import/SOAP flow — still reads credentials from the database internally on the server side.

---

## How can this be modified in the future?

**If you want to allow credential updates from the UI:**
Add a separate dedicated endpoint like `PUT /api/suppliers/{id}/credentials` that accepts new credentials but never returns them. The supplier detail page could have an "Update Credentials" button that opens a form with empty fields. Only if the admin fills in new values would it send them. This is the same pattern used by password change flows on any modern website — you can set a new password but you can never see the old one.

**If you need to show which fields are configured (without showing values):**
Instead of just `has_credentials: bool`, the backend could return `credentials_fields: ["id", "customer_number"]` — a list of which keys exist. This tells the UI "credentials are set for id and customer_number" without revealing the actual values.

---

## Files changed

| File | Type | Change |
|------|------|--------|
| `backend/modules/suppliers/schemas.py` | Backend | Removed `auth_config`, added `has_credentials: bool` |
| `backend/modules/suppliers/routes.py` | Backend | Set `has_credentials` in 4 response-building locations |
| `frontend/src/lib/types.ts` | Frontend | Updated `Supplier` interface to match new API shape |
| `frontend/src/app/(admin)/suppliers/[id]/page.tsx` | Frontend | Replaced editable credential fields with status panel |

---

## Manual Test Steps

### 1. Start the servers
```bash
# Terminal 1 — Backend
cd /Users/Vidhi/apihub/backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd /Users/Vidhi/apihub/frontend
npm run dev
```

### 2. Check the API response directly
```bash
curl http://localhost:8000/api/suppliers | python3 -m json.tool
```
**Expect:** `has_credentials: true/false` present. No `auth_config`, no `password`, no `id` field in the response.

### 3. Check the supplier detail page
- Go to `http://localhost:3000/suppliers`
- Click any supplier with credentials
- Scroll to "Authentication Credentials" section
- **Expect:** Green panel saying "Credentials configured". No input fields with passwords.

### 4. Verify save still works
- Change supplier name or toggle active status
- Click Save
- **Expect:** Saves without error. No credential fields sent in PATCH.
