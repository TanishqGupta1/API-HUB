# n8n Inline Product Push — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let any n8n instance push a complete product to a customer's OPS storefront in one authenticated call that both upserts the product into the catalog and runs the OPS mutation chain.

**Architecture:** Add an inline `product` (`ProductIngest`) to the existing `PushRequest`. When present, `prepare_push_intent` upserts it via `persist_product` (ON CONFLICT) and then reuses the existing reference-based resolve→preflight→`execute_push` path unchanged. Markup, OPS creds, and mappings stay hub-side. Result delivered via existing polling + callback webhook. Backend key-mint API already exists; only a frontend admin page is new.

**Tech Stack:** FastAPI, async SQLAlchemy + asyncpg, Pydantic v2, pytest/pytest-asyncio (httpx ASGITransport), Next.js 15 (App Router) + shadcn/ui + Tailwind.

**Source spec:** `plans/2026-06-01-n8n-inline-push-e2e.md`

**Conventions (from existing tests):** fixtures `client` (AsyncClient), `db`, `integration_key` (→ `{"key", "raw"}`), `push_scaffold` (→ `{"customer","product","supplier"}`), `seed_supplier`; autouse `_mock_preflight_ok` patches `modules.ops_push.gateway.run_preflight`. Hermetic tests use `@pytest.mark.no_db`; DB tests need Postgres on :5432 (run `docker compose up -d postgres`). Header: `X-Orchestrator-Key: <raw>`.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `backend/modules/integrations/schemas.py` | `PushRequest` gains typed inline `product`; validator; `PushRequestAccepted` gains `warnings` | Modify |
| `backend/modules/ops_push/gateway.py` | `prepare_push_intent` upserts inline product before resolve; surface warnings | Modify |
| `backend/modules/common/ssrf.py` | `assert_safe_url` (already exists) reused | Read |
| `backend/modules/ops_push/preflight.py:676-702` | guard image HEAD with `assert_safe_url` + `follow_redirects=False` | Modify |
| `backend/modules/ops_client/mutations.py` | contract fixes from Phase 0 | Modify |
| `backend/tests/test_gateway_inline_push.py` | inline-mode tests | Create |
| `backend/tests/test_preflight_ssrf.py` | SSRF guard tests | Create |
| `backend/tests/test_e2e_inline_push.py` | mint→push→poll→webhook e2e | Create |
| `frontend/src/app/(admin)/integration-keys/page.tsx` | keys admin UI | Create |
| `frontend/src/lib/types.ts` | `IntegrationKey` types | Modify |
| `n8n-workflows/ops-inline-push.json` | example workflow | Create |
| `docs/integration-guide-inline-push.md` | integration guide | Create |

---

## Task 0: Verify OPS mutation contracts (P0 — blocking for live pushes)

**Files:**
- Modify: `backend/modules/ops_client/mutations.py`
- Reference: OPS Postman collection (source of truth); `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` (working mutations)
- Doc: append results table to `plans/2026-06-01-n8n-inline-push-e2e.md` appendix

- [ ] **Step 1: Extract every mutation operation from `mutations.py`**

Run: `grep -nE "^mutation [A-Za-z]+" backend/modules/ops_client/mutations.py`
Expected: lists `SetProductCategory`, `SetProduct`, `SetProductSize`, `SetProductPrice`, `SetAssignOptions`, `SetAdditionalOption`, `SetAdditionalOptionAttributes`, `SetProductsAttributePrice`, `UpdateProductStock`, `SetProductDesign`.

- [ ] **Step 2: For each, diff against Postman + n8n node**

For each operation, compare three things: operation name, input type name (e.g. `setProduct_input!`), and the field set inside `input`. The working n8n node strings live in `n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts` (search the op name). The Postman collection is authoritative on input field names.

Run per op, e.g.: `grep -n "setProduct(" n8n-nodes-onprintshop/nodes/OnPrintShop.node.ts`

- [ ] **Step 3: Record verdicts in the appendix table**

Fill the table in `plans/2026-06-01-n8n-inline-push-e2e.md` (Appendix): `| Mutation | Postman op | Input type | Verdict | Notes |`. Verdict = CONFIRMED or MISMATCH(field/type diff).

- [ ] **Step 4: Fix each MISMATCH in `mutations.py`**

Apply the corrected query string / input field names. Show the exact before/after in the commit. Do not change `FakeOpsClient` (dry-run is contract-agnostic).

- [ ] **Step 5: Run ops_client tests + commit**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_ops_client_push.py -v`
Expected: PASS.
```bash
git add backend/modules/ops_client/mutations.py plans/2026-06-01-n8n-inline-push-e2e.md
git commit -m "fix(ops_client): align mutation contracts with OPS Postman collection"
```

---

## Task 1: Type the inline `product` field + validator

**Files:**
- Modify: `backend/modules/integrations/schemas.py:89-104` (`PushRequest`), `:32-43` (`PushRequestProductRef`)
- Test: `backend/tests/test_gateway_inline_push.py` (Create)

- [ ] **Step 1: Write failing schema test**

Create `backend/tests/test_gateway_inline_push.py`:
```python
"""Inline product push: PushRequest.product as ProductIngest + validator."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from modules.integrations.schemas import PushRequest

pytestmark = pytest.mark.no_db


def _ingest(sku="PC61-INLINE"):
    return {
        "supplier_sku": sku,
        "product_name": "Inline Tee",
        "product_type": "apparel",
        "apparel_details": {"fabric": "cotton"},
    }


def test_inline_product_parses_as_productingest():
    req = PushRequest.model_validate({
        "target": {"customer_id": "00000000-0000-0000-0000-000000000001"},
        "source": {"supplier_slug": "sanmar"},
        "product": _ingest(),
        "dry_run": True,
    })
    assert req.product is not None
    assert req.product.supplier_sku == "PC61-INLINE"
    # product_ref auto-derived from inline product
    assert req.product_ref.supplier_sku == "PC61-INLINE"


def test_neither_product_nor_ref_rejected():
    with pytest.raises(ValidationError):
        PushRequest.model_validate({
            "target": {"customer_id": "00000000-0000-0000-0000-000000000001"},
            "source": {"supplier_slug": "sanmar"},
        })


def test_ref_only_still_valid():
    req = PushRequest.model_validate({
        "target": {"customer_id": "00000000-0000-0000-0000-000000000001"},
        "source": {"supplier_slug": "sanmar"},
        "product_ref": {"supplier_sku": "EXISTING-SKU"},
    })
    assert req.product is None
    assert req.product_ref.supplier_sku == "EXISTING-SKU"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_gateway_inline_push.py -v`
Expected: FAIL — `product` is still `dict`, no validator deriving `product_ref`; `test_neither...` does not raise.

- [ ] **Step 3: Edit `schemas.py`**

At top of file ensure import: `from modules.catalog.schemas import ProductIngest`.
Replace the `PushRequest` class (`schemas.py:89`):
```python
class PushRequest(BaseModel):
    target: PushRequestTarget
    source: PushRequestSource
    product_ref: PushRequestProductRef = Field(default_factory=PushRequestProductRef)
    product: Optional[ProductIngest] = None   # inline upsert; when set, hub upserts then pushes
    decorations: list[dict[str, Any]] = Field(default_factory=list)
    dry_run: bool = False
    callback: Optional[PushRequestCallback] = None
    sync_before_push: bool = Field(
        default=False,
        description=(
            "When true, triggers an explicit_list sync for this product SKU "
            "before building the OPS payload. Adds ~5s latency but guarantees "
            "fresh inventory and pricing data at push time."
        ),
    )

    @model_validator(mode="after")
    def _require_product_or_ref(self) -> "PushRequest":
        has_ref = self.product_ref.product_id is not None or bool(self.product_ref.supplier_sku)
        if self.product is not None:
            # Inline mode: derive the ref so the existing resolver finds the upserted row.
            if not self.product_ref.supplier_sku:
                self.product_ref.supplier_sku = self.product.supplier_sku
            return self
        if not has_ref:
            raise ValueError("either `product` (inline) or `product_ref` must be provided")
        return self
```
Ensure `model_validator` is imported from pydantic at top (it is used elsewhere in this file).

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_gateway_inline_push.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**
```bash
git add backend/modules/integrations/schemas.py backend/tests/test_gateway_inline_push.py
git commit -m "feat(gateway): type inline PushRequest.product as ProductIngest with validator"
```

---

## Task 2: Upsert inline product in `prepare_push_intent`

**Files:**
- Modify: `backend/modules/ops_push/gateway.py:227-235` (after supplier resolve, before product resolve)
- Test: `backend/tests/test_gateway_inline_push.py` (add DB tests)

- [ ] **Step 1: Write failing DB test (append to test file)**

Append to `backend/tests/test_gateway_inline_push.py` (these need Postgres; remove `no_db` for them by putting in a separate class without the module marker — instead create a second file to keep the module-level `no_db`):

Create `backend/tests/test_gateway_inline_push_db.py`:
```python
"""Inline push DB path: product upserted then pushed (dry_run)."""
from __future__ import annotations

import hashlib
import secrets
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from database import async_session
from modules.catalog.models import Product
from modules.customers.models import Customer
from modules.integrations.models import IntegrationKey
from modules.push_log.models import ProductPushLog
from modules.suppliers.models import Supplier


@pytest.fixture(autouse=True)
def _mock_preflight_ok():
    ok = MagicMock()
    ok.ok = True
    ok.warnings = []
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=ok)):
        yield


@pytest_asyncio.fixture
async def key_and_customer(seed_supplier):
    raw = secrets.token_urlsafe(24)
    key_id = f"inline-key-{uuid4().hex[:8]}"
    async with async_session() as s:
        s.add(IntegrationKey(id=key_id, key_hash=hashlib.sha256(raw.encode()).hexdigest(), name="inline"))
        cust = Customer(
            name="Inline Co", ops_base_url="https://t.ops", ops_token_url="https://t.ops/tok",
            ops_client_id="x", ops_auth_config={"client_secret": "x"}, is_active=True,
        )
        s.add(cust)
        await s.commit()
        await s.refresh(cust)
        cid = cust.id
    try:
        yield {"raw": raw, "customer_id": cid, "supplier": seed_supplier}
    finally:
        async with async_session() as s:
            await s.execute(delete(ProductPushLog).where(ProductPushLog.customer_id == cid))
            await s.execute(delete(Product).where(Product.supplier_id == seed_supplier.id, Product.supplier_sku == "INLINE-1"))
            await s.execute(delete(Customer).where(Customer.id == cid))
            await s.execute(delete(IntegrationKey).where(IntegrationKey.id == key_id))
            await s.commit()


async def test_inline_dry_run_upserts_and_pushes(client, key_and_customer):
    ctx = key_and_customer
    body = {
        "target": {"customer_id": str(ctx["customer_id"])},
        "source": {"supplier_slug": ctx["supplier"].slug},
        "product": {
            "supplier_sku": "INLINE-1",
            "product_name": "Inline One",
            "product_type": "apparel",
            "apparel_details": {"fabric": "cotton"},
        },
        "dry_run": True,
    }
    r = await client.post("/api/integrations/v1/push-requests", json=body,
                          headers={"X-Orchestrator-Key": ctx["raw"]})
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "dry_run_pushed"
    # Catalog upsert happened
    async with async_session() as s:
        prod = (await s.execute(
            select(Product).where(Product.supplier_id == ctx["supplier"].id,
                                   Product.supplier_sku == "INLINE-1")
        )).scalar_one_or_none()
    assert prod is not None and prod.product_name == "Inline One"
```

- [ ] **Step 2: Run to verify it fails**

Run: `docker compose up -d postgres && cd backend && source .venv/bin/activate && pytest tests/test_gateway_inline_push_db.py -v`
Expected: FAIL — product not upserted (404 "Product not found in catalog") because inline upsert not wired.

- [ ] **Step 3: Wire the upsert in `gateway.py`**

In `prepare_push_intent`, immediately after the supplier-resolved block (after `gateway.py:234`, before the `# product_ref accepts...` comment at `:236`), insert:
```python
    # ── Inline product upsert ──
    # When the orchestrator ships the full product inline, upsert it into the
    # catalog first (ON CONFLICT DO UPDATE via persist_product), then fall
    # through to the normal resolve-from-catalog path. The validator already
    # set product_ref.supplier_sku from the inline product.
    if req.product is not None:
        from modules.catalog.persistence import persist_product
        await persist_product(db, supplier.id, req.product, category_id=None)
        await db.flush()
```
`pref = req.product_ref` (already at `:216`) now carries `supplier_sku`, so the existing resolver (`:251-255`) finds the just-upserted row.

- [ ] **Step 4: Run to verify pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_gateway_inline_push_db.py -v`
Expected: PASS (202, status dry_run_pushed, product row exists).

- [ ] **Step 5: Regression — ref-only path still works**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_gateway_push_request.py -v`
Expected: all PASS (no behavior change for `product_ref`-only callers).

- [ ] **Step 6: Commit**
```bash
git add backend/modules/ops_push/gateway.py backend/tests/test_gateway_inline_push_db.py
git commit -m "feat(gateway): upsert inline product before push (load+send in one call)"
```

---

## Task 3: Surface preflight warnings in the 202 response

**Files:**
- Modify: `backend/modules/integrations/schemas.py` (`PushRequestAccepted`), `backend/modules/ops_push/gateway.py:360-384`
- Test: `backend/tests/test_gateway_inline_push_db.py` (add)

> Blockers already cause a 422 with a `missing[]` envelope (`gateway.py:361-364`). This task surfaces non-blocking **warnings** in the accepted (202) body so n8n sees soft issues without polling.

- [ ] **Step 1: Failing test (append)**

Append to `backend/tests/test_gateway_inline_push_db.py`:
```python
async def test_inline_accept_includes_warnings_field(client, key_and_customer):
    ctx = key_and_customer
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(
        return_value=MagicMock(ok=True, warnings=[{"check": "markup", "message": "no rule; using passthrough"}])
    )):
        body = {
            "target": {"customer_id": str(ctx["customer_id"])},
            "source": {"supplier_slug": ctx["supplier"].slug},
            "product": {"supplier_sku": "INLINE-1", "product_name": "I1",
                        "product_type": "apparel", "apparel_details": {"fabric": "cotton"}},
            "dry_run": True,
        }
        r = await client.post("/api/integrations/v1/push-requests", json=body,
                              headers={"X-Orchestrator-Key": ctx["raw"]})
    assert r.status_code == 202
    assert r.json()["warnings"] == [{"check": "markup", "message": "no rule; using passthrough"}]
```

- [ ] **Step 2: Run to verify fail**

Run: `pytest tests/test_gateway_inline_push_db.py::test_inline_accept_includes_warnings_field -v`
Expected: FAIL — `warnings` key absent (KeyError / None).

- [ ] **Step 3: Add `warnings` to `PushRequestAccepted`**

In `schemas.py` `PushRequestAccepted` (`:113`), add field:
```python
    warnings: list[dict[str, Any]] = Field(default_factory=list)
```

- [ ] **Step 4: Populate it in `gateway.py`**

After the preflight block (`:360-364`), capture warnings and pass them into the `PushRequestAccepted` returned by this function and by the route. In `prepare_push_intent`, where `PushRequestAccepted(...)` is constructed for the accepted case, add `warnings=getattr(preflight, "warnings", []) or []`. (Apply to the non-replay accepted return only.)

- [ ] **Step 5: Run to verify pass**

Run: `pytest tests/test_gateway_inline_push_db.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add backend/modules/integrations/schemas.py backend/modules/ops_push/gateway.py backend/tests/test_gateway_inline_push_db.py
git commit -m "feat(gateway): surface preflight warnings in 202 accept body"
```

---

## Task 4: SSRF-guard inline image URLs (closes issue #147)

**Files:**
- Modify: `backend/modules/ops_push/preflight.py:674-702` (the `_head` probe)
- Test: `backend/tests/test_preflight_ssrf.py` (Create)

- [ ] **Step 1: Confirm `assert_safe_url` signature**

Run: `grep -nE "def assert_safe_url" backend/modules/common/ssrf.py`
Expected: a function that raises on private/loopback/link-local/metadata hosts (resolves DNS, checks all records).

- [ ] **Step 2: Write failing test**

Create `backend/tests/test_preflight_ssrf.py`:
```python
"""image_urls_reachable must SSRF-guard each URL before probing."""
from __future__ import annotations

import pytest

from modules.ops_push import preflight

pytestmark = pytest.mark.no_db


async def test_metadata_url_blocked_before_probe(monkeypatch):
    probed = []

    class _FakeClient:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def head(self, url, **k):
            probed.append(url)
            raise AssertionError("HEAD must not run on a blocked URL")

    monkeypatch.setattr(preflight.httpx, "AsyncClient", _FakeClient)

    result = await preflight.check_image_urls_reachable(
        ["http://169.254.169.254/latest/meta-data/"], dry_run=False, timeout_seconds=1.0
    )
    assert result.ok is False
    assert probed == []  # guarded before any outbound request
```
(Match `check_image_urls_reachable`'s real signature — confirm arg names via `grep -nE "def check_image_urls_reachable" backend/modules/ops_push/preflight.py` and adjust the call.)

- [ ] **Step 3: Run to verify fail**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_preflight_ssrf.py -v`
Expected: FAIL — current code calls `client.head(url, follow_redirects=True)` with no guard, so `probed` is non-empty (AssertionError raised inside HEAD).

- [ ] **Step 4: Guard the probe in `preflight.py`**

At top of `preflight.py` add: `from modules.common.ssrf import assert_safe_url`.
Replace the `_head` body (`:676-684`):
```python
    async def _head(url: str) -> tuple[str, bool, str]:
        async with sem:
            try:
                assert_safe_url(url)  # block metadata/private/loopback before any request
            except Exception as exc:  # noqa: BLE001
                return url, False, f"blocked_unsafe_url: {exc}"
            try:
                async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                    resp = await client.head(url, follow_redirects=False)
                ok = 200 <= resp.status_code < 300
                return url, ok, f"HTTP {resp.status_code}"
            except Exception as exc:  # noqa: BLE001
                return url, False, f"{exc.__class__.__name__}: {exc}"
```

- [ ] **Step 5: Run to verify pass**

Run: `cd backend && source .venv/bin/activate && pytest tests/test_preflight_ssrf.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**
```bash
git add backend/modules/ops_push/preflight.py backend/tests/test_preflight_ssrf.py
git commit -m "fix(preflight): SSRF-guard image HEAD probe, no redirect-follow (closes #147)"
```

---

## Task 5: Frontend — orchestrator-keys admin page  — ✅ ALREADY SATISFIED (no new code)

**Resolution (2026-06-02):** This page already exists on the `urvashi` branch as
`frontend/src/app/(admin)/integrations/page.tsx` (Vidhi's canonical version) and is
linked in the sidebar at `SidebarNav.tsx:198 → /integrations`. It implements list /
create / reveal-once / revoke against the existing `GET|POST /api/integrations/keys`
+ `/keys/{id}/revoke` endpoints, in Blueprint styling. `types.ts` carries an explicit
note that the duplicate `integration-keys/page.tsx` was **deliberately deleted** and
the types live in that page — so creating a second page would re-introduce a removed
duplicate. Task 5 is therefore complete; the only delta from the plan's wording is the
route name (`/integrations` rather than `/integration-keys`) and comma-separated
scope inputs instead of multiselect (acceptable UX equivalent).

**Files:**
- Create: `frontend/src/app/(admin)/integration-keys/page.tsx`
- Modify: `frontend/src/lib/types.ts` (add `IntegrationKey`, `IntegrationKeyCreated`)
- Reference: an existing admin page (e.g. `frontend/src/app/(admin)/markup/page.tsx`) for fetch + modal + Blueprint styling conventions.

> Backend already exists: `GET /api/integrations/keys`, `POST /api/integrations/keys` (returns `raw_key` once), `POST /api/integrations/keys/{id}/revoke`.

- [ ] **Step 1: Add types**

In `frontend/src/lib/types.ts` add:
```ts
export type IntegrationKey = {
  id: string;
  name: string;
  allowed_customer_ids: string[] | null;
  allowed_supplier_slugs: string[] | null;
  rate_limit_per_minute: number | null;
  is_active: boolean;
  last_used_at: string | null;
  created_at: string;
  revoked_at: string | null;
};
export type IntegrationKeyCreated = IntegrationKey & { raw_key: string };
```

- [ ] **Step 2: Build the page**

Create `frontend/src/app/(admin)/integration-keys/page.tsx` (client component). Mirror the fetch/modal pattern of `markup/page.tsx`. Required behaviors: list keys (mask: show `id`, `name`, scope, `last_used_at`, active badge); "Create key" modal with `name`, multiselect customers, multiselect suppliers; on create, show `raw_key` in a reveal-once banner with a copy button and a warning that it won't be shown again; "Revoke" button per active key. Use the existing `api()` helper from `@/lib/api`, Blueprint tokens (`btn`, `btn-ghost`, paper/blueprint palette), shadcn/ui components already in the repo. Gate the route behind vg_admin (follow how other `(admin)` pages enforce role).

- [ ] **Step 3: Add nav entry**

Add an "Integration Keys" link wherever the admin nav is defined (search: `grep -rn "markup" frontend/src/components | grep -i nav`). Match the existing nav item shape.

- [ ] **Step 4: Typecheck + build**

Run: `cd frontend && npx tsc --noEmit 2>&1 | grep -v "@sentry/nextjs"` → no new errors in the new file.
Run: `cd frontend && npm run build` → succeeds.

- [ ] **Step 5: Manual verify**

Start backend + frontend. Create a key → raw key shown once → reload page → raw key gone, key listed. Revoke → key marked inactive.

- [ ] **Step 6: Commit**
```bash
git add frontend/src/app/(admin)/integration-keys/page.tsx frontend/src/lib/types.ts frontend/src/components
git commit -m "feat(frontend): orchestrator-keys admin page (list/create/reveal-once/revoke)"
```

---

## Task 6: n8n example workflow + integration guide  — ✅ DONE (ref-based recipe)

**Resolution (2026-06-02):** Done, documenting the **working ref-based** path
(load via `POST /suppliers/{slug}/products`, then send via `POST /push-requests`
with `product_ref`), since the inline `product` upsert (Tasks 1–2) is not yet
wired on this branch. Both the workflow and the guide flag inline mode as
documented-but-pending so migrating later is a one-line body change. The guide
also accurately notes the callback is **not** yet HMAC-signed (the `secret` is
accepted but unused). Step 2 below: the JSON was validated as parseable and node/
connection-shaped against `sanmar-soap-pull.json`; a live n8n import was **not**
run in this environment.

**Files:**
- Create: `n8n-workflows/ops-inline-push.json`
- Create: `docs/integration-guide-inline-push.md`

- [x] **Step 1: Author the workflow JSON**

Create `n8n-workflows/ops-inline-push.json` — a minimal valid n8n workflow with: (a) a Manual/Trigger node, (b) an **HTTP Request** node `POST {{API_URL}}/api/integrations/v1/push-requests` with header `X-Orchestrator-Key` (credential ref) and JSON body containing `source`, `target`, `product` (ProductIngest), `dry_run`, `callback`; (c) a **Wait** + **HTTP Request** `GET .../push-requests/{{$json.push_log_id}}` poll loop branch; (d) a separate **Webhook** trigger node documenting the callback receiver. Mirror node JSON shape from an existing file in `n8n-workflows/` (e.g. `sanmar-soap-pull.json`).

- [x] **Step 2: Validate import** (JSON parse + node-shape validated; live n8n import not run here)

Import the JSON into a local n8n (`docker compose up -d n8n`, open :5678, import). Expected: imports without schema error.

- [x] **Step 3: Write the integration guide**

Create `docs/integration-guide-inline-push.md` covering: how to mint a key (admin UI), the `X-Orchestrator-Key` header, the full request body schema (link `GET /suppliers/{slug}/schema` discovery), a complete curl example (dry_run then live), every error code (`UNKNOWN_REF`, `INVALID_REF`, `SUPPLIER_MISMATCH`, `IDEMPOTENCY_CONFLICT`, `IN_FLIGHT`, `PREFLIGHT_BLOCKER`/422), `Idempotency-Key` semantics, polling (`GET /push-requests/{id}` terminal states) vs webhook callback (`X-ApiHub-Event`, HMAC), and the partial-failure contract (inline product is upserted even if an OPS mutation step fails → `push_log.status = partial_failure`).

- [ ] **Step 4: Commit**
```bash
git add n8n-workflows/ops-inline-push.json docs/integration-guide-inline-push.md
git commit -m "docs: n8n inline-push example workflow + integration guide"
```

---

## Task 7: End-to-end test (mint → push → poll → webhook)

**Files:**
- Create: `backend/tests/test_e2e_inline_push.py`

- [ ] **Step 1: Write the e2e test**

Create `backend/tests/test_e2e_inline_push.py`:
```python
"""E2E: mint key (DB) → inline live push (mocked OPS) → poll terminal → callback fired."""
from __future__ import annotations

import hashlib
import secrets
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy import delete

from database import async_session
from modules.catalog.models import Product
from modules.customers.models import Customer
from modules.integrations.models import IntegrationKey
from modules.push_log.models import ProductPushLog
from modules.push_mappings.models import PushMapping


@pytest.fixture(autouse=True)
def _preflight_ok():
    ok = MagicMock(ok=True, warnings=[])
    with patch("modules.ops_push.gateway.run_preflight", new=AsyncMock(return_value=ok)):
        yield


@pytest_asyncio.fixture
async def scaffold(seed_supplier):
    raw = secrets.token_urlsafe(24)
    kid = f"e2e-{uuid4().hex[:8]}"
    async with async_session() as s:
        s.add(IntegrationKey(id=kid, key_hash=hashlib.sha256(raw.encode()).hexdigest(), name="e2e"))
        cust = Customer(name="E2E", ops_base_url="https://t.ops", ops_token_url="https://t.ops/t",
                        ops_client_id="x", ops_auth_config={"client_secret": "x"}, is_active=True)
        s.add(cust); await s.commit(); await s.refresh(cust); cid = cust.id
    try:
        yield {"raw": raw, "customer_id": cid, "supplier": seed_supplier}
    finally:
        async with async_session() as s:
            await s.execute(delete(PushMapping).where(PushMapping.customer_id == cid))
            await s.execute(delete(ProductPushLog).where(ProductPushLog.customer_id == cid))
            await s.execute(delete(Product).where(Product.supplier_id == seed_supplier.id, Product.supplier_sku == "E2E-1"))
            await s.execute(delete(Customer).where(Customer.id == cid))
            await s.execute(delete(IntegrationKey).where(IntegrationKey.id == kid))
            await s.commit()


async def test_inline_live_push_polls_terminal(client, scaffold):
    ctx = scaffold
    body = {
        "target": {"customer_id": str(ctx["customer_id"])},
        "source": {"supplier_slug": ctx["supplier"].slug},
        "product": {"supplier_sku": "E2E-1", "product_name": "E2E One",
                    "product_type": "apparel", "apparel_details": {"fabric": "cotton"}},
        "dry_run": False,
    }
    # Mock the live OPS client so no real GraphQL call is made.
    fake = MagicMock()
    fake.execute = AsyncMock(return_value=MagicMock(data={"setProduct": {"products_id": 999}}, raw={}))
    with patch("modules.ops_push.gateway._build_live_client", return_value=fake):
        r = await client.post("/api/integrations/v1/push-requests", json=body,
                              headers={"X-Orchestrator-Key": ctx["raw"]})
        assert r.status_code == 202, r.text
        pid = r.json()["push_log_id"]
        # background task runs in-process; poll until terminal
        poll = await client.get(f"/api/integrations/v1/push-requests/{pid}",
                                headers={"X-Orchestrator-Key": ctx["raw"]})
    assert poll.status_code == 200
    assert poll.json()["status"] in ("pushed", "partial_failure", "failed")
```

- [ ] **Step 2: Run**

Run: `docker compose up -d postgres && cd backend && source .venv/bin/activate && pytest tests/test_e2e_inline_push.py -v`
Expected: PASS (terminal status reached; adjust the `_build_live_client` patch target / fake shape if the dispatcher expects different return — confirm against `gateway.py:462-517`).

- [ ] **Step 3: Commit**
```bash
git add backend/tests/test_e2e_inline_push.py
git commit -m "test(gateway): e2e inline push — mint→push→poll terminal"
```

---

## Final verification (run after all tasks)

- [ ] `docker compose up -d postgres && cd backend && source .venv/bin/activate && pytest -q` — all green.
- [ ] `cd backend && python -c "import main"` — imports.
- [ ] `cd frontend && npm run build` — clean (excl. pre-existing `@sentry/nextjs`).
- [ ] Manual smoke: mint key in UI → curl inline dry-run → live (mock or staging) → poll terminal → webhook received.

## Self-review notes
- Spec coverage: Task 0=Phase0, Task1-2=Phase1 inline mode, Task3=preflight-in-202 (warnings), Task4=Phase2 SSRF/#147, Task5=Phase3 UI, Task6=Phase4 docs/workflow, Task7=Phase5 e2e. All spec phases mapped.
- Type consistency: `product` (ProductIngest), `product_ref` (optional, validator-derived), `warnings` (list[dict]) used consistently across schema + tests.
- Known confirm-at-impl points (flagged inline, not placeholders): exact arg names of `check_image_urls_reachable` (Task 4 Step 2) and the live-client dispatch return shape (Task 7 Step 2) — each task says to confirm via the cited grep/line before finalizing.
