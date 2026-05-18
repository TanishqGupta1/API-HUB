# Milestone Plan T7 — Supplier Form Schema Audit

## What this task is

**Backend + Frontend.** T7 audits the supplier create form and compares what it sends against what the `SupplierCreate` Pydantic schema accepts. Fixes any fields that are silently dropped or cause validation errors.

---

## How it relates to the existing project

The new supplier form at `/suppliers/new` sends a POST to `POST /api/suppliers`. The backend validates the body against `SupplierCreate` in `backend/modules/suppliers/schemas.py`. If a field the frontend sends is not in the schema, Pydantic drops it silently. If a field has the wrong enum value, Pydantic returns a 422 — the supplier is never created.

---

## What was broken

### Bug 1 — `adapter_class` silently dropped on create

The frontend sends `adapter_class` in the POST payload. The `Supplier` model has an `adapter_class` column (`String(64)`). But `SupplierCreate` did not include `adapter_class`, so:

- Pydantic stripped it from the validated body
- `payload = body.model_dump()` never contained it
- `Supplier(**payload)` never set the column
- The adapter class the user selected was lost — the supplier was saved with `adapter_class = NULL` even if the user picked one

### Bug 2 — Protocol `"rest_hmac"` fails validation (4Over)

`Protocol` Literal was:
```python
Literal["soap", "rest", "hmac", "ops_graphql", "promostandards"]
```

The frontend form used `value: "rest_hmac"` for the "REST + HMAC — 4Over" option. Since `"rest_hmac"` is not in the Literal, any attempt to create a 4Over supplier returned a **422 Unprocessable Entity**.

### Bug 3 — Protocol `"sftp"` fails validation (SanMar SFTP)

The frontend form had `value: "sftp"` for the "SFTP / CSV — SanMar" option. `"sftp"` was not in the Literal at all — same 422 result.

---

## What changed

### `backend/modules/suppliers/schemas.py`

1. Added `"sftp"` to the `Protocol` Literal:
```python
Protocol = Literal["soap", "rest", "hmac", "ops_graphql", "promostandards", "sftp"]
```

2. Added `adapter_class` to `SupplierCreate`:
```python
class SupplierCreate(BaseModel):
    name: str
    slug: str
    protocol: Protocol
    promostandards_code: Optional[str] = None
    base_url: Optional[str] = None
    adapter_class: Optional[str] = None   # ← added
    auth_config: dict = Field(default_factory=dict)
```

### `frontend/src/app/(admin)/suppliers/new/page.tsx`

Changed the 4Over protocol value from `"rest_hmac"` to `"hmac"` to match the backend Literal:
```tsx
// Before (broken):
{ value: "rest_hmac", label: "REST + HMAC — 4Over", ... }

// After (correct):
{ value: "hmac", label: "REST + HMAC — 4Over", ... }
```

---

## Why it was necessary

- Without the `adapter_class` fix: users who selected an adapter class on the create form would see it vanish after save. They would have to go back to the detail page and re-select it via PATCH — which did work, since `_SUPPLIER_PATCHABLE` already included `adapter_class`.
- Without the protocol fixes: creating a 4Over or SanMar SFTP supplier would silently fail with a 422 error from the backend, with no meaningful UI feedback.

---

## What was already correct

- **PATCH** (`PATCH /api/suppliers/{id}`) takes `body: dict` with an explicit `_SUPPLIER_PATCHABLE` allowlist — no Pydantic schema, so `adapter_class`, `is_active`, `field_mappings`, and `protocol_config` all worked correctly on edit.
- The `Supplier` model columns were already correct — the bugs were entirely in the schema/frontend layer.

---

## How it can be modified in the future

When adding a new supplier protocol:
1. Add the protocol string to the `Protocol` Literal in `schemas.py`
2. Add a `ProtocolDef` entry in `PROTOCOLS` array in `suppliers/new/page.tsx`
3. Make sure the `value` in the frontend exactly matches the string in the Literal

When adding a new top-level supplier field:
1. Add it to the `Supplier` SQLAlchemy model
2. Add it to `SupplierCreate` (for POST) and `SupplierRead` (for GET responses)
3. Add it to `_SUPPLIER_PATCHABLE` in `routes.py` (for PATCH)
