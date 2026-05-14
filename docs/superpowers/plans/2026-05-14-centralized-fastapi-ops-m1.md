# Centralized FastAPI OPS Push + Ingest (M1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move OPS GraphQL mutation knowledge out of n8n into FastAPI. After this lands, any caller (n8n, curl, Zapier, Lambda) pushes SanMar→OPS via one HTTP endpoint.

**Architecture:** New `backend/modules/ops_client/` (typed GraphQL transport + 7 mutation wrappers + push orchestrator). New `backend/modules/integration_gateway/` (9 endpoints under `/api/integrations/v1/`, `X-Orchestrator-Key` auth, idempotency ledger). Admin route + frontend repoint to gateway. Old n8n push workflows deleted.

**Tech Stack:** FastAPI, SQLAlchemy async, httpx, Pydantic v2, pytest, Next.js 15 (TypeScript), shadcn/ui, Tailwind.

**Spec:** [`docs/superpowers/specs/2026-05-13-centralized-fastapi-ops-design.md`](../specs/2026-05-13-centralized-fastapi-ops-design.md)

---

## File Structure

### New backend files
- `backend/modules/ops_client/__init__.py` — package
- `backend/modules/ops_client/client.py` — OAuth-aware GraphQL transport, typed `OpsResult`
- `backend/modules/ops_client/mutations.py` — 7 OPS mutation wrappers
- `backend/modules/ops_client/push.py` — `push_apparel_product` orchestrator (ID threading)
- `backend/modules/ops_client/fake.py` — `FakeOpsClient` for dry_run + tests
- `backend/modules/integration_gateway/__init__.py` — package
- `backend/modules/integration_gateway/auth.py` — `X-Orchestrator-Key` dependency + scope check
- `backend/modules/integration_gateway/idempotency.py` — payload-hash ledger
- `backend/modules/integration_gateway/schemas.py` — request/response envelopes
- `backend/modules/integration_gateway/routes.py` — 9 endpoints
- `backend/modules/integration_gateway/service.py` — orchestration helpers
- `backend/tests/test_ops_client_mutations.py` — mutation wrapper unit tests
- `backend/tests/test_ops_client_push.py` — ID threading + happy/failure paths
- `backend/tests/test_gateway_auth.py` — `X-Orchestrator-Key` enforcement + scope
- `backend/tests/test_gateway_idempotency.py` — same-key same-payload + 409 conflict
- `backend/tests/test_gateway_push_dry_run.py` — full PC61 push payload via FakeOpsClient
- `backend/tests/test_gateway_admin_route_preserved.py` — admin response shape post-rewire

### Modified backend files
- `backend/modules/auth/dependencies.py` — collapse `require_ingest_secret()` to constant-time compare (pre-M1)
- `backend/modules/catalog/ingest.py:57-61` — point to single matcher (pre-M1)
- `backend/modules/master_options/routes.py:11` — drop `n8n_proxy` import (pre-M1)
- `backend/modules/suppliers/routes.py:166-196` — real test-connection probe (pre-M1)
- `backend/modules/ops_push/service.py` — dispatch to ops_client; drop `trigger_n8n_push`
- `backend/modules/ops_push/merge.py` — shrink to hub-domain merge (OPS field mapping moves to ops_client)
- `backend/modules/markup/routes.py:32-90` — collapse 3 endpoints into single payload endpoint
- `backend/main.py` — register integration_gateway router

### Modified frontend files
- `frontend/src/lib/push-status.ts` — NEW central status-map for 9-value vocab
- `frontend/src/lib/types.ts:374` — broaden `SelectionStatus` union to 9 values
- `frontend/src/components/products/push-row-action.tsx:53-56` — POST gateway instead of n8n
- `frontend/src/components/SelectionBadge.tsx` — use status-map
- `frontend/src/components/products/push-history.tsx:55-63` — use status-map
- `frontend/src/app/(admin)/customers/[id]/catalog/page.tsx` — use status-map
- `frontend/src/app/(admin)/push-log/page.tsx:21-31` — use status-map

### Deleted in M1.5
- `n8n-workflows/ops-push.json`
- `n8n-workflows/ops-master-options-pull.json`
- `backend/modules/ops_push/service.py::trigger_n8n_push` function only
- `backend/modules/ops_push/merge.py` (or shrunk to hub-domain only)
- `N8N_PUSH_WEBHOOK_URL` env var references

---

## M1.0 — Pre-M1 cleanup (4 tasks)

### Task 1: Refactor `master_options/routes.py` away from `n8n_proxy`

**Files:**
- Modify: `backend/modules/master_options/routes.py`
- Modify: `backend/modules/n8n_proxy/routes.py` (extract helper)
- Test: `backend/tests/test_master_options_sync.py`

Reason: M4 deletes `n8n_proxy/`. Today `master_options/routes.py:11` imports `trigger_workflow_by_id` from there. Pre-empt the break by moving the helper.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_master_options_sync.py
import pytest
from fastapi.testclient import TestClient
from main import app
from unittest.mock import AsyncMock, patch

def test_master_options_sync_uses_direct_n8n_helper(monkeypatch):
    monkeypatch.setenv("N8N_API_BASE_URL", "http://n8n:5678")
    monkeypatch.setenv("N8N_API_KEY", "test")
    monkeypatch.setenv("OPS_MASTER_OPTIONS_WORKFLOW_ID", "test-wf-001")

    with patch("modules.master_options.routes._trigger_n8n_workflow", new_callable=AsyncMock) as mock_trigger:
        mock_trigger.return_value = {"triggered": True, "url": "x", "response": {}}
        client = TestClient(app)
        # ... auth setup ...
        resp = client.post("/api/master-options/sync")
    assert mock_trigger.called
```

- [ ] **Step 2: Run test, verify it fails**

```bash
cd backend && pytest tests/test_master_options_sync.py -v
```

Expected: FAIL — `_trigger_n8n_workflow` not defined.

- [ ] **Step 3: Move helper into `master_options/routes.py`**

```python
# backend/modules/master_options/routes.py — top of file
import os
import httpx
from fastapi import APIRouter, HTTPException

async def _trigger_n8n_workflow(workflow_id: str, params: dict | None = None) -> dict:
    """Trigger an n8n workflow by ID. Standalone helper — does not import n8n_proxy."""
    base = os.getenv("N8N_API_BASE_URL") or os.getenv("N8N_BASE_URL") or "http://n8n:5678"
    base = base.rstrip("/")
    api_key = os.getenv("N8N_API_KEY")
    if not api_key:
        raise HTTPException(500, "N8N_API_KEY not configured")

    async with httpx.AsyncClient(timeout=10.0) as hc:
        wf = await hc.get(f"{base}/api/v1/workflows/{workflow_id}", headers={"X-N8N-API-KEY": api_key})
        wf.raise_for_status()
        nodes = wf.json().get("nodes", [])
        webhook_node = next((n for n in nodes if n.get("type") == "n8n-nodes-base.webhook"), None)
        if not webhook_node:
            raise HTTPException(404, f"No webhook trigger in workflow {workflow_id}")
        webhook_path = webhook_node["parameters"]["path"]

    webhook_base = (os.getenv("N8N_WEBHOOK_BASE_URL") or base).rstrip("/")
    trigger_url = f"{webhook_base}/webhook/{webhook_path}"
    async with httpx.AsyncClient(timeout=10.0) as hc:
        tr = await hc.post(trigger_url, json=params or {})
        tr.raise_for_status()
        return {"triggered": True, "url": trigger_url, "response": tr.json() if tr.text else {}}
```

Then replace existing usage:

```python
# backend/modules/master_options/routes.py — find the line that imports n8n_proxy
# OLD:
#     from modules.n8n_proxy.routes import trigger_workflow_by_id
# NEW: (delete the import; use local _trigger_n8n_workflow)

# In the /sync handler, replace:
#     await trigger_workflow_by_id(workflow_id)
# with:
#     await _trigger_n8n_workflow(workflow_id)
```

- [ ] **Step 4: Run test, verify it passes**

```bash
cd backend && pytest tests/test_master_options_sync.py -v
```

Expected: PASS.

- [ ] **Step 5: Verify no other importers**

```bash
grep -rn "from modules.n8n_proxy" backend/
```

Expected output: only `backend/main.py:37,202` (router registration + lifecycle close). Master options no longer in this list.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/master_options/routes.py backend/tests/test_master_options_sync.py
git commit -m "refactor(master_options): drop n8n_proxy import; local helper

Preempts M4 deletion of modules/n8n_proxy. master_options now owns its
n8n trigger helper standalone."
```

---

### Task 2: Collapse `require_ingest_secret` to constant-time compare

**Files:**
- Modify: `backend/modules/catalog/ingest.py:57-61`
- Modify: `backend/modules/auth/dependencies.py` (export helper)
- Test: `backend/tests/test_ingest_secret_constant_time.py`

Reason: `catalog/ingest.py:57-61` still uses raw `==` for secret compare. Security parity with PR #106 fix.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_ingest_secret_constant_time.py
import hmac
from modules.auth.dependencies import _ingest_secret_matches

def test_ingest_secret_matches_uses_hmac(monkeypatch):
    monkeypatch.setenv("INGEST_SHARED_SECRET", "correct-secret")
    assert _ingest_secret_matches("correct-secret") is True
    assert _ingest_secret_matches("wrong-secret") is False
    assert _ingest_secret_matches(None) is False
    assert _ingest_secret_matches("") is False

def test_require_ingest_secret_imports_from_auth():
    import inspect
    from modules.catalog import ingest
    src = inspect.getsource(ingest.require_ingest_secret)
    # Function body must use the auth.dependencies matcher, not raw ==
    assert "_ingest_secret_matches" in src or "compare_digest" in src
    assert " == expected" not in src
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && pytest tests/test_ingest_secret_constant_time.py -v
```

- [ ] **Step 3: Edit `catalog/ingest.py:57-61`**

```python
# backend/modules/catalog/ingest.py — replace the existing require_ingest_secret
from modules.auth.dependencies import _ingest_secret_matches

def require_ingest_secret(x_ingest_secret: str | None = Header(None, alias="X-Ingest-Secret")) -> None:
    if not _ingest_secret_matches(x_ingest_secret):
        raise HTTPException(status_code=401, detail="Invalid or missing X-Ingest-Secret")
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && pytest tests/test_ingest_secret_constant_time.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/catalog/ingest.py backend/tests/test_ingest_secret_constant_time.py
git commit -m "fix(security): collapse require_ingest_secret to hmac.compare_digest

Carries the PR #106 X-Ingest-Secret fix into catalog/ingest.py.
Eliminates remaining raw-== secret comparison."
```

---

### Task 3: Real SanMar SOAP test-connection probe

**Files:**
- Modify: `backend/modules/suppliers/routes.py:166-196`
- Modify: `backend/modules/promostandards/client.py` (add `validate_credentials` helper)
- Test: `backend/tests/test_supplier_real_test_connection.py`

Reason: Today `/api/suppliers/test` only checks PS directory membership. Real onboarding gets green light then import fails. Add an actual SOAP auth probe.

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_supplier_real_test_connection.py
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from main import app

def test_test_connection_calls_promostandards_validate(monkeypatch):
    monkeypatch.setenv("INGEST_SHARED_SECRET", "test")
    client = TestClient(app)

    with patch(
        "modules.promostandards.client.PromoStandardsClient.validate_credentials",
        new_callable=AsyncMock,
    ) as mock_validate:
        mock_validate.return_value = {"ok": True, "endpoint": "https://sanmar/ProductDataService"}
        resp = client.post(
            "/api/suppliers/test",
            json={
                "protocol": "promostandards",
                "promostandards_code": "SANMAR",
                "auth_config": {"id": "x", "password": "y"},
            },
            headers={"X-Ingest-Secret": "test"},
        )
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    assert mock_validate.called


def test_test_connection_returns_real_error_on_bad_creds(monkeypatch):
    monkeypatch.setenv("INGEST_SHARED_SECRET", "test")
    client = TestClient(app)

    with patch(
        "modules.promostandards.client.PromoStandardsClient.validate_credentials",
        new_callable=AsyncMock,
    ) as mock_validate:
        mock_validate.return_value = {"ok": False, "error": "401 Unauthorized"}
        resp = client.post(
            "/api/suppliers/test",
            json={
                "protocol": "promostandards",
                "promostandards_code": "SANMAR",
                "auth_config": {"id": "wrong", "password": "wrong"},
            },
            headers={"X-Ingest-Secret": "test"},
        )
    body = resp.json()
    assert body["ok"] is False
    assert "401" in body["error"]
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && pytest tests/test_supplier_real_test_connection.py -v
```

Expected: FAIL (`validate_credentials` attribute missing OR endpoint returns fake check).

- [ ] **Step 3: Add `validate_credentials` to `PromoStandardsClient`**

```python
# backend/modules/promostandards/client.py — append a method
class PromoStandardsClient:
    # ... existing methods ...

    async def validate_credentials(self) -> dict:
        """Probe live SOAP endpoint with current creds. Returns {ok, endpoint?, error?}."""
        try:
            # Smallest possible authenticated call — getProductSellable with limit=1
            # If id/password are wrong, SOAP returns 401 or a SOAP fault.
            result = await self.get_product_sellable_minimal()
            return {"ok": True, "endpoint": self._endpoint("PRODUCT")}
        except Exception as exc:
            return {"ok": False, "error": str(exc)[:300]}
```

- [ ] **Step 4: Rewrite `/api/suppliers/test` to dispatch by protocol**

```python
# backend/modules/suppliers/routes.py — replace test_supplier_connection (around line 166-196)
from modules.promostandards.client import PromoStandardsClient

@router.post("/test")
async def test_supplier_connection(
    body: SupplierTestRequest,
    _: User = Depends(get_current_user),
) -> dict:
    """Real per-protocol auth probe. Returns {ok, error?, endpoint?}."""
    protocol = (body.protocol or "").lower()
    auth = body.auth_config or {}

    if protocol == "promostandards":
        code = (body.promostandards_code or "").upper()
        if not code:
            return {"ok": False, "error": "promostandards_code required"}
        if not auth.get("id") or not auth.get("password"):
            return {"ok": False, "error": "id and password required"}
        client = PromoStandardsClient(code=code, id_=auth["id"], password=auth["password"])
        return await client.validate_credentials()

    # 4Over, S&S, OPS — wired in later phases; for now indicate not implemented
    return {"ok": False, "error": f"test-connection not implemented for protocol={protocol!r}"}
```

- [ ] **Step 5: Run, verify PASS**

```bash
cd backend && pytest tests/test_supplier_real_test_connection.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/modules/suppliers/routes.py backend/modules/promostandards/client.py \
  backend/tests/test_supplier_real_test_connection.py
git commit -m "feat(suppliers): real SanMar SOAP test-connection probe

Replaces the directory-only check with an actual authenticated SOAP
call via PromoStandardsClient.validate_credentials. Other protocols
return 'not implemented' until their adapters expose a probe."
```

---

### Task 4: Frontend central status-map

**Files:**
- Create: `frontend/src/lib/push-status.ts`
- Modify: `frontend/src/lib/types.ts:374`

Reason: Today 9 status values from spec break UI. 16 hardcoded sites. Create central map first so subsequent tasks plug into it.

- [ ] **Step 1: Write the status-map file**

```typescript
// frontend/src/lib/push-status.ts
export type PushStatus =
  | "selected"
  | "accepted"
  | "queued"
  | "processing"
  | "pushed"
  | "failed"
  | "partial_failure"
  | "rejected"
  | "canceled"
  | "dry_run_pushed"
  | "stale";

export interface StatusMeta {
  label: string;
  badgeClass: string;     // Tailwind classes for shadcn Badge
  dotPulse?: boolean;     // true for in-flight states
  description?: string;
}

export const PUSH_STATUS: Record<PushStatus, StatusMeta> = {
  selected:        { label: "Selected",        badgeClass: "bg-slate-100 text-slate-700 border-slate-200" },
  accepted:        { label: "Accepted",        badgeClass: "bg-blue-50 text-blue-700 border-blue-200", dotPulse: true },
  queued:          { label: "Queued",          badgeClass: "bg-blue-50 text-blue-700 border-blue-200", dotPulse: true },
  processing:      { label: "Processing",      badgeClass: "bg-blue-100 text-blue-800 border-blue-300", dotPulse: true },
  pushed:          { label: "Pushed",          badgeClass: "bg-emerald-50 text-emerald-700 border-emerald-200" },
  failed:          { label: "Failed",          badgeClass: "bg-rose-50 text-rose-700 border-rose-200" },
  partial_failure: { label: "Partial Failure", badgeClass: "bg-amber-50 text-amber-700 border-amber-200" },
  rejected:        { label: "Rejected",        badgeClass: "bg-rose-50 text-rose-700 border-rose-200" },
  canceled:        { label: "Canceled",        badgeClass: "bg-slate-100 text-slate-500 border-slate-200" },
  dry_run_pushed:  { label: "Dry-Run OK",      badgeClass: "bg-violet-50 text-violet-700 border-violet-200" },
  stale:           { label: "Stale",           badgeClass: "bg-amber-50 text-amber-700 border-amber-200" },
};

export function getStatusMeta(status: string): StatusMeta {
  return PUSH_STATUS[status as PushStatus] ?? {
    label: status,
    badgeClass: "bg-slate-100 text-slate-700 border-slate-200",
  };
}

export const TERMINAL_STATUSES: PushStatus[] = ["pushed", "failed", "rejected", "canceled", "dry_run_pushed"];
export const IN_FLIGHT_STATUSES: PushStatus[] = ["accepted", "queued", "processing"];

export function isTerminal(status: string): boolean {
  return TERMINAL_STATUSES.includes(status as PushStatus);
}

export function isInFlight(status: string): boolean {
  return IN_FLIGHT_STATUSES.includes(status as PushStatus);
}
```

- [ ] **Step 2: Broaden `SelectionStatus` union**

```typescript
// frontend/src/lib/types.ts:374 — replace the existing line
// OLD: export type SelectionStatus = "selected" | "pushed" | "stale" | "failed";
// NEW:
export type SelectionStatus =
  | "selected" | "accepted" | "queued" | "processing"
  | "pushed" | "failed" | "partial_failure" | "rejected"
  | "canceled" | "dry_run_pushed" | "stale";
```

- [ ] **Step 3: Verify build**

```bash
cd frontend && npx tsc --noEmit
```

Expected: no errors related to push-status.ts.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/push-status.ts frontend/src/lib/types.ts
git commit -m "feat(frontend): central push-status map + 9-value SelectionStatus

Adds frontend/src/lib/push-status.ts as single source of truth for
push log status badges, labels, and in-flight detection. Broadens
SelectionStatus union from 4 to 11 values per gateway spec status
vocab. Subsequent tasks plug components into this map."
```

---

## M1.1 — ops_client module (7 tasks)

### Task 5: `ops_client/client.py` — typed transport scaffold

**Files:**
- Create: `backend/modules/ops_client/__init__.py`
- Create: `backend/modules/ops_client/client.py`
- Test: `backend/tests/test_ops_client_transport.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_ops_client_transport.py
import pytest
from modules.ops_client.client import OpsAuth, OpsResult, OpsGraphQLClient

def test_ops_auth_is_frozen_dataclass():
    auth = OpsAuth(
        base_url="https://store.test",
        token_url="https://store.test/oauth/token",
        client_id="cid",
        client_secret="csec",
    )
    with pytest.raises(Exception):  # FrozenInstanceError
        auth.base_url = "x"  # type: ignore

def test_ops_result_carries_error():
    r = OpsResult(ok=False, data=None, ops_error_code="GRAPHQL_ERROR",
                  ops_error_message="bad input", raw={"errors": []})
    assert r.ok is False
    assert r.ops_error_code == "GRAPHQL_ERROR"

@pytest.mark.asyncio
async def test_client_constructable():
    auth = OpsAuth(base_url="https://x", token_url="https://x/t", client_id="a", client_secret="b")
    client = OpsGraphQLClient(auth=auth)
    assert client.auth is auth
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && pytest tests/test_ops_client_transport.py -v
```

- [ ] **Step 3: Implement client**

```python
# backend/modules/ops_client/__init__.py — empty
```

```python
# backend/modules/ops_client/client.py
from __future__ import annotations
import time
import httpx
import logging
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("ops_client")


@dataclass(frozen=True)
class OpsAuth:
    base_url: str
    token_url: str
    client_id: str
    client_secret: str


@dataclass(frozen=True)
class OpsResult:
    ok: bool
    data: dict[str, Any] | None = None
    ops_error_code: str | None = None
    ops_error_message: str | None = None
    raw: dict[str, Any] | None = None


class OpsGraphQLClient:
    """OAuth-aware GraphQL client for OnPrintShop.

    Caches access token in-memory per instance until expiry. Each push
    request constructs a fresh client (creds resolved from EncryptedJSON
    on customer row).
    """

    GRAPHQL_PATH = "/graphql"

    def __init__(self, auth: OpsAuth, *, timeout_seconds: float = 30.0):
        self.auth = auth
        self._timeout = timeout_seconds
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    async def _get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expires_at - 30:
            return self._token
        async with httpx.AsyncClient(timeout=self._timeout) as hc:
            resp = await hc.post(
                self.auth.token_url,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self.auth.client_id,
                    "client_secret": self.auth.client_secret,
                },
            )
            resp.raise_for_status()
            body = resp.json()
        self._token = body["access_token"]
        ttl = int(body.get("expires_in", 3600))
        self._token_expires_at = now + ttl
        return self._token

    async def execute(self, query: str, *, variables: dict[str, Any]) -> OpsResult:
        token = await self._get_token()
        url = f"{self.auth.base_url.rstrip('/')}{self.GRAPHQL_PATH}"
        async with httpx.AsyncClient(timeout=self._timeout) as hc:
            resp = await hc.post(
                url,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json={"query": query, "variables": variables},
            )
        try:
            body = resp.json()
        except ValueError:
            return OpsResult(ok=False, ops_error_code="NON_JSON_RESPONSE",
                             ops_error_message=resp.text[:300], raw=None)

        if resp.status_code >= 400 or body.get("errors"):
            errors = body.get("errors") or [{"message": f"HTTP {resp.status_code}"}]
            first = errors[0]
            return OpsResult(
                ok=False,
                ops_error_code=first.get("extensions", {}).get("code", "GRAPHQL_ERROR"),
                ops_error_message=first.get("message", "")[:300],
                raw=body,
            )
        return OpsResult(ok=True, data=body.get("data"), raw=body)
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && pytest tests/test_ops_client_transport.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ops_client/ backend/tests/test_ops_client_transport.py
git commit -m "feat(ops_client): typed GraphQL transport with OAuth token cache

Foundation for M1: OpsAuth + OpsResult dataclasses + OpsGraphQLClient
with client-credentials OAuth flow and in-memory token caching.
Returns typed OpsResult on every call — never raises on GraphQL errors."
```

---

### Task 6: Mutation wrapper — `set_product_category`

**Files:**
- Modify: `backend/modules/ops_client/mutations.py` (create)
- Test: `backend/tests/test_ops_client_mutations.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_ops_client_mutations.py
import pytest
from unittest.mock import AsyncMock
from modules.ops_client.client import OpsGraphQLClient, OpsResult, OpsAuth
from modules.ops_client import mutations as m

@pytest.fixture
def fake_client():
    c = OpsGraphQLClient(OpsAuth(base_url="x", token_url="y", client_id="a", client_secret="b"))
    c.execute = AsyncMock()
    return c

@pytest.mark.asyncio
async def test_set_product_category_sends_canonical_fields(fake_client):
    fake_client.execute.return_value = OpsResult(ok=True, data={
        "setProductCategory": {"category_id": 42}
    })
    result = await m.set_product_category(
        client=fake_client, category_name="T-Shirts", parent_id=0, visible=1,
    )
    assert result.ok
    # Verify the GraphQL variables contain OPS field names exactly
    _, kwargs = fake_client.execute.call_args
    vars = kwargs["variables"]
    assert vars["input"]["category_name"] == "T-Shirts"
    assert vars["input"]["parent_id"] == 0
    assert vars["input"]["visible"] == 1

@pytest.mark.asyncio
async def test_set_product_category_extracts_id(fake_client):
    fake_client.execute.return_value = OpsResult(ok=True, data={
        "setProductCategory": {"category_id": 99}
    })
    result = await m.set_product_category(
        client=fake_client, category_name="X", parent_id=0, visible=1,
    )
    assert result.ok
    assert result.data["category_id"] == 99
```

- [ ] **Step 2: Run, verify FAIL**

```bash
cd backend && pytest tests/test_ops_client_mutations.py::test_set_product_category_sends_canonical_fields -v
```

- [ ] **Step 3: Implement mutation wrapper**

```python
# backend/modules/ops_client/mutations.py
from __future__ import annotations
from .client import OpsGraphQLClient, OpsResult

_SET_PRODUCT_CATEGORY = """
mutation SetProductCategory($input: setProductCategory_input!) {
  setProductCategory(input: $input) {
    category_id
  }
}
"""

async def set_product_category(
    *,
    client: OpsGraphQLClient,
    category_name: str,
    parent_id: int = 0,
    visible: int = 1,
) -> OpsResult:
    """Returns OpsResult.data = {category_id: int} on success."""
    result = await client.execute(
        _SET_PRODUCT_CATEGORY,
        variables={"input": {
            "category_name": category_name,
            "parent_id": parent_id,
            "visible": visible,
        }},
    )
    if not result.ok:
        return result
    inner = (result.data or {}).get("setProductCategory") or {}
    return OpsResult(ok=True, data=inner, raw=result.raw)
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && pytest tests/test_ops_client_mutations.py::test_set_product_category_sends_canonical_fields \
                  tests/test_ops_client_mutations.py::test_set_product_category_extracts_id -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ops_client/mutations.py backend/tests/test_ops_client_mutations.py
git commit -m "feat(ops_client): set_product_category mutation wrapper

Returns OpsResult with extracted category_id on success. GraphQL
input shape matches n8n node canonical fields (category_name, parent_id,
visible)."
```

---

### Task 7: Mutation wrapper — `set_product`

**Files:**
- Modify: `backend/modules/ops_client/mutations.py`
- Modify: `backend/tests/test_ops_client_mutations.py`

- [ ] **Step 1: Add failing test**

```python
# backend/tests/test_ops_client_mutations.py — append

@pytest.mark.asyncio
async def test_set_product_threads_category_id(fake_client):
    fake_client.execute.return_value = OpsResult(ok=True, data={
        "setProduct": {"products_id": 12345}
    })
    result = await m.set_product(
        client=fake_client,
        category_id=42,
        products_title="Port & Company PC61",
        products_internal_title="PC61",
        visible=1,
    )
    _, kwargs = fake_client.execute.call_args
    vars = kwargs["variables"]["input"]
    assert vars["category_id"] == 42
    assert vars["products_title"] == "Port & Company PC61"
    assert vars["products_internal_title"] == "PC61"
    assert vars["visible"] == 1
    assert result.data["products_id"] == 12345
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Append to `mutations.py`**

```python
_SET_PRODUCT = """
mutation SetProduct($input: setProduct_input!) {
  setProduct(input: $input) {
    products_id
  }
}
"""

async def set_product(
    *,
    client: OpsGraphQLClient,
    category_id: int,
    products_title: str,
    products_internal_title: str,
    visible: int = 1,
) -> OpsResult:
    """Returns OpsResult.data = {products_id: int}."""
    result = await client.execute(
        _SET_PRODUCT,
        variables={"input": {
            "category_id": category_id,
            "products_title": products_title,
            "products_internal_title": products_internal_title,
            "visible": visible,
        }},
    )
    if not result.ok:
        return result
    inner = (result.data or {}).get("setProduct") or {}
    return OpsResult(ok=True, data=inner, raw=result.raw)
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ops_client/mutations.py backend/tests/test_ops_client_mutations.py
git commit -m "feat(ops_client): set_product mutation wrapper

Threads category_id from setProductCategory. Maps backend product.name
→ products_title and product.supplier_sku → products_internal_title."
```

---

### Task 8: Mutation wrapper — `set_product_size`

**Files:**
- Modify: `backend/modules/ops_client/mutations.py`
- Modify: `backend/tests/test_ops_client_mutations.py`

- [ ] **Step 1: Add failing test**

```python
@pytest.mark.asyncio
async def test_set_product_size_threads_products_id(fake_client):
    fake_client.execute.return_value = OpsResult(ok=True, data={
        "setProductSize": {"size_id": 555}
    })
    result = await m.set_product_size(
        client=fake_client,
        products_id=12345,
        size_name="M",
        color_name="Navy",
        products_sku="PC61-NAV-M",
        visible=1,
    )
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["products_id"] == 12345
    assert v["size_name"] == "M"
    assert v["color_name"] == "Navy"
    assert v["products_sku"] == "PC61-NAV-M"
    assert result.data["size_id"] == 555
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Append to `mutations.py`**

```python
_SET_PRODUCT_SIZE = """
mutation SetProductSize($input: setProductSize_input!) {
  setProductSize(input: $input) {
    size_id
  }
}
"""

async def set_product_size(
    *,
    client: OpsGraphQLClient,
    products_id: int,
    size_name: str,
    color_name: str,
    products_sku: str,
    visible: int = 1,
) -> OpsResult:
    """Returns OpsResult.data = {size_id: int}."""
    result = await client.execute(
        _SET_PRODUCT_SIZE,
        variables={"input": {
            "products_id": products_id,
            "size_name": size_name,
            "color_name": color_name,
            "products_sku": products_sku,
            "visible": visible,
        }},
    )
    if not result.ok:
        return result
    inner = (result.data or {}).get("setProductSize") or {}
    return OpsResult(ok=True, data=inner, raw=result.raw)
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ops_client/mutations.py backend/tests/test_ops_client_mutations.py
git commit -m "feat(ops_client): set_product_size mutation wrapper

Returns size_id for caller to thread into setProductPrice. One call
per variant."
```

---

### Task 9: Mutation wrapper — `set_product_price`

**Files:**
- Modify: `backend/modules/ops_client/mutations.py`
- Modify: `backend/tests/test_ops_client_mutations.py`

- [ ] **Step 1: Add failing test**

```python
@pytest.mark.asyncio
async def test_set_product_price_threads_products_id_and_size_id(fake_client):
    fake_client.execute.return_value = OpsResult(ok=True, data={
        "setProductPrice": {"product_price_id": 7777}
    })
    result = await m.set_product_price(
        client=fake_client,
        products_id=12345,
        size_id=555,
        qty=1,
        qty_to=None,
        price="9.99",
        vendor_price="3.99",
        visible=1,
    )
    _, kwargs = fake_client.execute.call_args
    v = kwargs["variables"]["input"]
    assert v["products_id"] == 12345
    assert v["size_id"] == 555
    assert v["price"] == "9.99"
    assert v["vendor_price"] == "3.99"
    assert result.ok
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Append to `mutations.py`**

```python
_SET_PRODUCT_PRICE = """
mutation SetProductPrice($input: setProductPrice_input!) {
  setProductPrice(input: $input) {
    product_price_id
  }
}
"""

async def set_product_price(
    *,
    client: OpsGraphQLClient,
    products_id: int,
    size_id: int,
    price: str,
    vendor_price: str,
    qty: int = 1,
    qty_to: int | None = None,
    visible: int = 1,
) -> OpsResult:
    """Per-variant price row. Accepts price strings to preserve Decimal precision."""
    input_dict = {
        "products_id": products_id,
        "size_id": size_id,
        "qty": qty,
        "price": price,
        "vendor_price": vendor_price,
        "visible": visible,
    }
    if qty_to is not None:
        input_dict["qty_to"] = qty_to
    result = await client.execute(_SET_PRODUCT_PRICE, variables={"input": input_dict})
    if not result.ok:
        return result
    inner = (result.data or {}).get("setProductPrice") or {}
    return OpsResult(ok=True, data=inner, raw=result.raw)
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ops_client/mutations.py backend/tests/test_ops_client_mutations.py
git commit -m "feat(ops_client): set_product_price mutation wrapper

Per-variant price with size_id threading. Accepts price as string to
preserve Decimal precision through the JSON boundary."
```

---

### Task 10: `ops_client/fake.py` — `FakeOpsClient` for dry_run + tests

**Files:**
- Create: `backend/modules/ops_client/fake.py`
- Test: `backend/tests/test_ops_client_fake.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_ops_client_fake.py
import pytest
from modules.ops_client.fake import FakeOpsClient

@pytest.mark.asyncio
async def test_fake_client_returns_synthetic_ids_in_order():
    c = FakeOpsClient()
    r1 = await c.execute("mutation SetProductCategory(...)", variables={"input": {"category_name": "X"}})
    r2 = await c.execute("mutation SetProduct(...)", variables={"input": {"category_id": r1.data["setProductCategory"]["category_id"]}})
    assert r1.ok and r1.data["setProductCategory"]["category_id"] > 0
    assert r2.ok and r2.data["setProduct"]["products_id"] > 0

@pytest.mark.asyncio
async def test_fake_client_records_calls():
    c = FakeOpsClient()
    await c.execute("mutation SetProduct(...)", variables={"input": {"products_title": "PC61"}})
    assert len(c.calls) == 1
    assert c.calls[0]["mutation_name"] == "SetProduct"
    assert c.calls[0]["variables"]["input"]["products_title"] == "PC61"
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

```python
# backend/modules/ops_client/fake.py
from __future__ import annotations
import re
from typing import Any
from .client import OpsResult


_MUTATION_NAME_RE = re.compile(r"mutation\s+(\w+)")


class FakeOpsClient:
    """In-memory OPS double for dry_run + tests. Returns synthetic IDs."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self._next_id = 1000

    def _allocate_id(self) -> int:
        i = self._next_id
        self._next_id += 1
        return i

    async def execute(self, query: str, *, variables: dict[str, Any]) -> OpsResult:
        match = _MUTATION_NAME_RE.search(query)
        name = match.group(1) if match else "Unknown"
        self.calls.append({"mutation_name": name, "variables": variables})

        if name == "SetProductCategory":
            return OpsResult(ok=True, data={"setProductCategory": {"category_id": self._allocate_id()}})
        if name == "SetProduct":
            return OpsResult(ok=True, data={"setProduct": {"products_id": self._allocate_id()}})
        if name == "SetProductSize":
            return OpsResult(ok=True, data={"setProductSize": {"size_id": self._allocate_id()}})
        if name == "SetProductPrice":
            return OpsResult(ok=True, data={"setProductPrice": {"product_price_id": self._allocate_id()}})
        if name == "SetAdditionalOption":
            return OpsResult(ok=True, data={"setAdditionalOption": {"prod_add_opt_id": self._allocate_id()}})
        if name == "SetAdditionalOptionAttributes":
            return OpsResult(ok=True, data={"setAdditionalOptionAttributes": {"attribute_id": self._allocate_id()}})
        if name == "SetProductsAttributePrice":
            return OpsResult(ok=True, data={"setProductsAttributePrice": {"ok": True}})
        return OpsResult(ok=False, ops_error_code="UNKNOWN_MUTATION", ops_error_message=name)
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ops_client/fake.py backend/tests/test_ops_client_fake.py
git commit -m "feat(ops_client): FakeOpsClient for dry_run + tests

In-memory double that allocates synthetic IDs and records every call.
Used for dry_run=true push requests and for contract tests."
```

---

### Task 11: `ops_client/push.py` — `push_apparel_product` orchestrator

**Files:**
- Create: `backend/modules/ops_client/push.py`
- Test: `backend/tests/test_ops_client_push.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_ops_client_push.py
import pytest
from decimal import Decimal
from modules.ops_client.fake import FakeOpsClient
from modules.ops_client.push import push_apparel_product
from modules.catalog.schemas import ProductIngest, VariantIngest

@pytest.mark.asyncio
async def test_push_apparel_threads_ids_across_4_mutations():
    fake = FakeOpsClient()
    product = ProductIngest(
        supplier_sku="PC61",
        product_name="Port & Company Essential Tee",
        category_name="T-Shirts",
        variants=[
            VariantIngest(part_id="PC61-NAV-S", sku="PC61-NAV-S",
                          color="Navy", size="S", base_price=Decimal("3.99")),
            VariantIngest(part_id="PC61-NAV-M", sku="PC61-NAV-M",
                          color="Navy", size="M", base_price=Decimal("3.99")),
        ],
    )
    result = await push_apparel_product(client=fake, product=product, final_prices={
        "PC61-NAV-S": Decimal("9.99"),
        "PC61-NAV-M": Decimal("9.99"),
    })
    assert result["ok"]
    assert result["ops_product_id"] > 0
    # Mutations called in correct order
    names = [c["mutation_name"] for c in fake.calls]
    assert names[0] == "SetProductCategory"
    assert names[1] == "SetProduct"
    assert names.count("SetProductSize") == 2
    assert names.count("SetProductPrice") == 2

    # IDs threaded correctly
    cat_id = fake.calls[0]
    prod_call = next(c for c in fake.calls if c["mutation_name"] == "SetProduct")
    assert "category_id" in prod_call["variables"]["input"]
    assert prod_call["variables"]["input"]["category_id"] > 0
    size_calls = [c for c in fake.calls if c["mutation_name"] == "SetProductSize"]
    for sc in size_calls:
        assert sc["variables"]["input"]["products_id"] > 0
    price_calls = [c for c in fake.calls if c["mutation_name"] == "SetProductPrice"]
    for pc in price_calls:
        assert pc["variables"]["input"]["size_id"] > 0


@pytest.mark.asyncio
async def test_push_apparel_halt_on_failure():
    """If setProductSize fails on variant 2, status='partial_failure' with cleanup_targets."""
    from modules.ops_client.client import OpsResult
    fake = FakeOpsClient()
    real_execute = fake.execute
    call_idx = [0]

    async def flaky(query, *, variables):
        call_idx[0] += 1
        # Fail on the 4th call (second SetProductSize)
        if call_idx[0] == 4:
            return OpsResult(ok=False, ops_error_code="OPS_VALIDATION",
                             ops_error_message="duplicate sku")
        return await real_execute(query, variables=variables)
    fake.execute = flaky

    product = ProductIngest(
        supplier_sku="PC61", product_name="X", category_name="T-Shirts",
        variants=[
            VariantIngest(part_id="A", sku="A", color="X", size="S"),
            VariantIngest(part_id="B", sku="B", color="X", size="M"),
        ],
    )
    result = await push_apparel_product(client=fake, product=product,
                                        final_prices={"A": Decimal("9.99"), "B": Decimal("9.99")})
    assert not result["ok"]
    assert result["status"] == "partial_failure"
    assert result["ops_product_id"] > 0  # was created before halt
    assert len(result["cleanup_targets"]) > 0
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement orchestrator**

```python
# backend/modules/ops_client/push.py
from __future__ import annotations
from decimal import Decimal
from typing import Any
from modules.catalog.schemas import ProductIngest
from .client import OpsGraphQLClient, OpsResult
from . import mutations as m


async def push_apparel_product(
    *,
    client: OpsGraphQLClient,
    product: ProductIngest,
    final_prices: dict[str, Decimal],
) -> dict[str, Any]:
    """Execute the 4-step apparel push with halt-no-rollback.

    Returns:
        {
            "ok": bool,
            "status": "pushed" | "partial_failure" | "failed",
            "ops_product_id": int | None,
            "ops_category_id": int | None,
            "size_id_by_sku": dict[str, int],
            "step_results": list[dict],   # for push_log.step_results JSONB
            "cleanup_targets": list[dict],  # for push_log.cleanup_targets
            "error": str | None,
        }

    `final_prices` keys are variant.sku; values are marked-up final prices.
    """
    step_results: list[dict[str, Any]] = []
    cleanup_targets: list[dict[str, Any]] = []
    size_id_by_sku: dict[str, int] = {}
    ops_category_id: int | None = None
    ops_product_id: int | None = None

    def _record(step: str, ok: bool, **extra: Any) -> None:
        step_results.append({"step": step, "ok": ok, **extra})

    # Step 1: setProductCategory
    r = await m.set_product_category(
        client=client,
        category_name=product.category_name or "Uncategorized",
        parent_id=0,
        visible=1,
    )
    if not r.ok:
        _record("set_product_category", False, error=r.ops_error_message)
        return {
            "ok": False, "status": "failed",
            "ops_product_id": None, "ops_category_id": None,
            "size_id_by_sku": {}, "step_results": step_results,
            "cleanup_targets": [], "error": r.ops_error_message,
        }
    ops_category_id = r.data["category_id"]
    _record("set_product_category", True, category_id=ops_category_id)

    # Step 2: setProduct
    r = await m.set_product(
        client=client,
        category_id=ops_category_id,
        products_title=product.product_name,
        products_internal_title=product.supplier_sku,
        visible=1,
    )
    if not r.ok:
        _record("set_product", False, error=r.ops_error_message)
        # Category was created; track for manual cleanup if desired
        cleanup_targets.append({"ops_category_id": ops_category_id})
        return {
            "ok": False, "status": "failed",
            "ops_product_id": None, "ops_category_id": ops_category_id,
            "size_id_by_sku": {}, "step_results": step_results,
            "cleanup_targets": cleanup_targets, "error": r.ops_error_message,
        }
    ops_product_id = r.data["products_id"]
    _record("set_product", True, products_id=ops_product_id)

    # Step 3: setProductSize per variant
    for variant in product.variants:
        if not variant.sku:
            _record("set_product_size", False, error=f"variant {variant.part_id} missing sku")
            continue
        r = await m.set_product_size(
            client=client,
            products_id=ops_product_id,
            size_name=variant.size or "",
            color_name=variant.color or "",
            products_sku=variant.sku,
            visible=1,
        )
        if not r.ok:
            _record("set_product_size", False, sku=variant.sku, error=r.ops_error_message)
            cleanup_targets.append({"ops_product_id": ops_product_id})
            for sku, sid in size_id_by_sku.items():
                cleanup_targets.append({"ops_size_id": sid, "sku": sku})
            return {
                "ok": False, "status": "partial_failure",
                "ops_product_id": ops_product_id, "ops_category_id": ops_category_id,
                "size_id_by_sku": size_id_by_sku, "step_results": step_results,
                "cleanup_targets": cleanup_targets, "error": r.ops_error_message,
            }
        size_id_by_sku[variant.sku] = r.data["size_id"]
        _record("set_product_size", True, sku=variant.sku, size_id=r.data["size_id"])

    # Step 4: setProductPrice per variant
    for variant in product.variants:
        if not variant.sku or variant.sku not in size_id_by_sku:
            continue
        final = final_prices.get(variant.sku)
        if final is None or variant.base_price is None:
            _record("set_product_price", False, sku=variant.sku,
                    error="missing final_price or base_price")
            continue
        r = await m.set_product_price(
            client=client,
            products_id=ops_product_id,
            size_id=size_id_by_sku[variant.sku],
            price=str(final),
            vendor_price=str(variant.base_price),
            qty=1,
            visible=1,
        )
        if not r.ok:
            _record("set_product_price", False, sku=variant.sku, error=r.ops_error_message)
            cleanup_targets.append({"ops_product_id": ops_product_id})
            return {
                "ok": False, "status": "partial_failure",
                "ops_product_id": ops_product_id, "ops_category_id": ops_category_id,
                "size_id_by_sku": size_id_by_sku, "step_results": step_results,
                "cleanup_targets": cleanup_targets, "error": r.ops_error_message,
            }
        _record("set_product_price", True, sku=variant.sku)

    return {
        "ok": True, "status": "pushed",
        "ops_product_id": ops_product_id, "ops_category_id": ops_category_id,
        "size_id_by_sku": size_id_by_sku, "step_results": step_results,
        "cleanup_targets": [], "error": None,
    }
```

- [ ] **Step 4: Run, verify PASS**

```bash
cd backend && pytest tests/test_ops_client_push.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/ops_client/push.py backend/tests/test_ops_client_push.py
git commit -m "feat(ops_client): push_apparel_product orchestrator with halt-no-rollback

4-step ID-threaded push: setProductCategory → setProduct → setProductSize
(per variant) → setProductPrice (per variant). On any failure after
setProduct succeeds, halt and return cleanup_targets so operator can
delete stranded OPS rows manually. Status flips to partial_failure on
mid-stream failure, failed if nothing reached OPS."
```

---

## M1.2 — integration_gateway module (5 tasks)

### Task 12: `integration_gateway/auth.py` — X-Orchestrator-Key dependency

**Files:**
- Create: `backend/modules/integration_gateway/__init__.py`
- Create: `backend/modules/integration_gateway/auth.py`
- Test: `backend/tests/test_gateway_auth.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_gateway_auth.py
import pytest
from fastapi import FastAPI, Depends, HTTPException
from fastapi.testclient import TestClient
from modules.integration_gateway.auth import require_orchestrator_key, OrchestratorContext

@pytest.fixture
def app(monkeypatch):
    monkeypatch.setenv("INTEGRATION_KEY_oh-test", "raw-key-abc")
    app = FastAPI()
    @app.get("/x")
    async def x(ctx: OrchestratorContext = Depends(require_orchestrator_key)):
        return {"key_id": ctx.key_id}
    return app

def test_missing_header_returns_401(app):
    client = TestClient(app)
    r = client.get("/x")
    assert r.status_code == 401

def test_wrong_key_returns_403(app):
    client = TestClient(app)
    r = client.get("/x", headers={"X-Orchestrator-Key": "wrong"})
    assert r.status_code == 403

def test_correct_key_returns_context(app):
    client = TestClient(app)
    r = client.get("/x", headers={"X-Orchestrator-Key": "raw-key-abc"})
    assert r.status_code == 200
    assert r.json()["key_id"] == "oh-test"
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

```python
# backend/modules/integration_gateway/__init__.py — empty
```

```python
# backend/modules/integration_gateway/auth.py
from __future__ import annotations
import hmac
import os
from dataclasses import dataclass
from typing import Annotated

from fastapi import Header, HTTPException, status


@dataclass(frozen=True)
class OrchestratorContext:
    key_id: str
    raw_key: str  # never log


def _find_matching_key(provided: str) -> str | None:
    """Walk INTEGRATION_KEY_* env vars; return key_id whose value matches.

    Env var name pattern: INTEGRATION_KEY_<key_id>=<raw_secret>
    Constant-time compare prevents timing leak.
    """
    if not provided:
        return None
    prefix = "INTEGRATION_KEY_"
    for name, val in os.environ.items():
        if not name.startswith(prefix):
            continue
        if val and hmac.compare_digest(provided.encode("utf-8"), val.encode("utf-8")):
            return name[len(prefix):]
    return None


async def require_orchestrator_key(
    x_orchestrator_key: Annotated[str | None, Header(alias="X-Orchestrator-Key")] = None,
) -> OrchestratorContext:
    if not x_orchestrator_key:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing X-Orchestrator-Key")
    key_id = _find_matching_key(x_orchestrator_key)
    if not key_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid X-Orchestrator-Key")
    return OrchestratorContext(key_id=key_id, raw_key=x_orchestrator_key)
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/modules/integration_gateway/__init__.py \
  backend/modules/integration_gateway/auth.py \
  backend/tests/test_gateway_auth.py
git commit -m "feat(gateway): X-Orchestrator-Key auth dependency

Env-driven key registry (INTEGRATION_KEY_<id>=<raw>) with constant-time
compare. Returns OrchestratorContext to handler. DB-backed integration_keys
table comes later in M0 — for now env is the source of truth."
```

---

### Task 13: `integration_gateway/idempotency.py` — payload-hash ledger

**Files:**
- Create: `backend/modules/integration_gateway/idempotency.py`
- Test: `backend/tests/test_gateway_idempotency.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_gateway_idempotency.py
import pytest
from modules.integration_gateway.idempotency import (
    compute_payload_hash, check_idempotency,
)

def test_payload_hash_is_deterministic():
    body = {"a": 1, "b": [1, 2]}
    assert compute_payload_hash(body) == compute_payload_hash({"b": [1, 2], "a": 1})

def test_payload_hash_changes_on_diff():
    assert compute_payload_hash({"a": 1}) != compute_payload_hash({"a": 2})

@pytest.mark.asyncio
async def test_idempotency_new_key_returns_none(db_session):
    decision = await check_idempotency(
        db=db_session, key_id="oh-test", idempotency_key="abc",
        payload_hash=compute_payload_hash({"x": 1}),
    )
    assert decision.action == "proceed"
    assert decision.existing_push_log_id is None

@pytest.mark.asyncio
async def test_idempotency_same_key_same_payload_returns_existing(db_session):
    payload = {"x": 1}
    h = compute_payload_hash(payload)
    # First call records
    first = await check_idempotency(
        db=db_session, key_id="oh-test", idempotency_key="abc", payload_hash=h,
        record_push_log_id="11111111-1111-1111-1111-111111111111",
    )
    second = await check_idempotency(
        db=db_session, key_id="oh-test", idempotency_key="abc", payload_hash=h,
    )
    assert second.action == "return_existing"
    assert str(second.existing_push_log_id) == "11111111-1111-1111-1111-111111111111"

@pytest.mark.asyncio
async def test_idempotency_same_key_different_payload_conflicts(db_session):
    await check_idempotency(
        db=db_session, key_id="oh-test", idempotency_key="abc",
        payload_hash=compute_payload_hash({"x": 1}),
        record_push_log_id="11111111-1111-1111-1111-111111111111",
    )
    second = await check_idempotency(
        db=db_session, key_id="oh-test", idempotency_key="abc",
        payload_hash=compute_payload_hash({"x": 2}),
    )
    assert second.action == "conflict"
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement (writes to `product_push_log` columns added in M0)**

```python
# backend/modules/integration_gateway/idempotency.py
from __future__ import annotations
import hashlib
import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.push_log.models import ProductPushLog


def compute_payload_hash(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IdempotencyDecision:
    action: str  # "proceed" | "return_existing" | "conflict"
    existing_push_log_id: UUID | None = None


async def check_idempotency(
    *,
    db: AsyncSession,
    key_id: str,
    idempotency_key: str,
    payload_hash: str,
    record_push_log_id: UUID | str | None = None,
) -> IdempotencyDecision:
    """Look up (key_id, idempotency_key) on product_push_log.

    If found with same payload_hash → return_existing.
    If found with different payload_hash → conflict.
    Else → proceed (and optionally record the new push_log_id).
    """
    stmt = (
        select(ProductPushLog)
        .where(
            ProductPushLog.key_id == key_id,
            ProductPushLog.idempotency_key == idempotency_key,
        )
        .order_by(ProductPushLog.pushed_at.desc())
        .limit(1)
    )
    row = (await db.execute(stmt)).scalar_one_or_none()
    if row is None:
        return IdempotencyDecision(action="proceed")
    if row.payload_hash == payload_hash:
        return IdempotencyDecision(action="return_existing", existing_push_log_id=row.id)
    return IdempotencyDecision(action="conflict", existing_push_log_id=row.id)
```

- [ ] **Step 4: Run, verify PASS** (requires M0 columns in DB — assume migration ran or use a stub for tests)

```bash
cd backend && pytest tests/test_gateway_idempotency.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/integration_gateway/idempotency.py backend/tests/test_gateway_idempotency.py
git commit -m "feat(gateway): payload-hash idempotency ledger

sha256 over canonical JSON. check_idempotency returns proceed /
return_existing / conflict based on (key_id, idempotency_key) lookup
on product_push_log. M0 migration adds the required columns
(idempotency_key, payload_hash, key_id)."
```

---

### Task 14: `integration_gateway/schemas.py` — request/response envelopes

**Files:**
- Create: `backend/modules/integration_gateway/schemas.py`
- Test: `backend/tests/test_gateway_schemas.py`

- [ ] **Step 1: Write failing test**

```python
# backend/tests/test_gateway_schemas.py
import pytest
from pydantic import ValidationError
from modules.integration_gateway.schemas import (
    PushRequest, PushRequestTarget, PushRequestSource, PushRequestProductRef,
)

def test_push_request_minimal_valid():
    req = PushRequest(
        target=PushRequestTarget(customer_id="11111111-1111-1111-1111-111111111111"),
        source=PushRequestSource(supplier_slug="sanmar"),
        product_ref=PushRequestProductRef(product_id="22222222-2222-2222-2222-222222222222"),
        dry_run=False,
    )
    assert req.dry_run is False

def test_push_request_rejects_missing_target():
    with pytest.raises(ValidationError):
        PushRequest(  # type: ignore
            source=PushRequestSource(supplier_slug="sanmar"),
            product_ref=PushRequestProductRef(product_id="x"),
        )
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement**

```python
# backend/modules/integration_gateway/schemas.py
from __future__ import annotations
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PushRequestTarget(BaseModel):
    system: Literal["ops"] = "ops"
    customer_id: UUID


class PushRequestSource(BaseModel):
    supplier_slug: str


class PushRequestProductRef(BaseModel):
    product_id: Optional[UUID] = None
    supplier_sku: Optional[str] = None


class PushRequestCallback(BaseModel):
    url: str
    secret: Optional[str] = None


class PushRequest(BaseModel):
    target: PushRequestTarget
    source: PushRequestSource
    product_ref: PushRequestProductRef
    decorations: list[dict] = Field(default_factory=list)
    dry_run: bool = False
    callback: Optional[PushRequestCallback] = None


class PushRequestAccepted(BaseModel):
    push_log_id: UUID
    status: str
    customer_id: UUID
    supplier_slug: str
    supplier_sku: Optional[str] = None
    ops_product_id: Optional[str] = None
    dry_run: bool
    callback_status: str
    created_at: datetime


class PushRequestStatus(BaseModel):
    push_log_id: UUID
    status: str
    customer_id: UUID
    supplier_slug: str
    supplier_sku: Optional[str] = None
    ops_product_id: Optional[str] = None
    mapping_id: Optional[UUID] = None
    error: Optional[str] = None
    step_results: list[dict] = Field(default_factory=list)
    cleanup_targets: list[dict] = Field(default_factory=list)
    callback_status: str
    callback_attempts: int = 0
    finished_at: Optional[datetime] = None


class ErrorEnvelope(BaseModel):
    status: Literal["error"] = "error"
    code: str
    message: str
    details: dict = Field(default_factory=dict)
    trace_id: Optional[str] = None
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git add backend/modules/integration_gateway/schemas.py backend/tests/test_gateway_schemas.py
git commit -m "feat(gateway): request/response envelope Pydantic models

PushRequest + PushRequestAccepted + PushRequestStatus + ErrorEnvelope.
Matches Rev 3 spec exactly. Pydantic v2 with ConfigDict."
```

---

### Task 15: `integration_gateway/routes.py` — POST /push-requests

**Files:**
- Create: `backend/modules/integration_gateway/routes.py`
- Create: `backend/modules/integration_gateway/service.py`
- Test: `backend/tests/test_gateway_push_dry_run.py`

- [ ] **Step 1: Write failing test (dry_run path)**

```python
# backend/tests/test_gateway_push_dry_run.py
import pytest
from fastapi.testclient import TestClient
from main import app

def test_push_dry_run_with_pc61_returns_accepted(seeded_db, sanmar_pc61_product, vg_customer, monkeypatch):
    monkeypatch.setenv("INTEGRATION_KEY_oh-test", "raw-key-abc")
    client = TestClient(app)
    r = client.post(
        "/api/integrations/v1/push-requests",
        headers={"X-Orchestrator-Key": "raw-key-abc",
                 "Idempotency-Key": "test-pc61-dry-001"},
        json={
            "target":      {"customer_id": str(vg_customer.id)},
            "source":      {"supplier_slug": "sanmar"},
            "product_ref": {"product_id": str(sanmar_pc61_product.id)},
            "dry_run":     True,
        },
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "dry_run_pushed"
    assert body["dry_run"] is True
    assert "push_log_id" in body
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Implement routes + service**

```python
# backend/modules/integration_gateway/service.py
from __future__ import annotations
from decimal import Decimal
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.catalog.models import Product
from modules.customers.models import Customer
from modules.suppliers.models import Supplier
from modules.markup.engine import calculate_price
from modules.ops_client.client import OpsAuth, OpsGraphQLClient
from modules.ops_client.fake import FakeOpsClient
from modules.ops_client.push import push_apparel_product


async def resolve_product_to_ingest(db: AsyncSession, product_id: UUID):
    """Load Product + variants from DB and convert to ProductIngest shape."""
    from modules.catalog.schemas import ProductIngest, VariantIngest
    row = await db.get(Product, product_id)
    if not row:
        return None
    # Load variants ... (use existing relationship)
    variants = [
        VariantIngest(
            part_id=v.part_id, sku=v.sku, color=v.color, size=v.size,
            base_price=v.base_price, inventory=v.inventory,
        )
        for v in row.variants
    ]
    return ProductIngest(
        supplier_sku=row.supplier_sku,
        product_name=row.product_name,
        category_name=row.category,
        brand=row.brand,
        variants=variants,
    )


def build_ops_client(customer: Customer, *, fake: bool = False):
    if fake:
        return FakeOpsClient()
    auth_config = customer.ops_auth_config or {}
    auth = OpsAuth(
        base_url=auth_config["store_url"],
        token_url=auth_config["token_url"],
        client_id=auth_config["client_id"],
        client_secret=auth_config["client_secret"],
    )
    return OpsGraphQLClient(auth=auth)


async def compute_final_prices(db: AsyncSession, customer_id: UUID, product) -> dict[str, Decimal]:
    """Apply markup engine per variant. Returns sku → final_price."""
    out: dict[str, Decimal] = {}
    for v in product.variants:
        if v.sku and v.base_price is not None:
            out[v.sku] = await calculate_price(
                db=db, customer_id=customer_id, base_price=v.base_price,
                supplier_id=None, category=product.category_name,
            )
    return out
```

```python
# backend/modules/integration_gateway/routes.py
from __future__ import annotations
import logging
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from modules.customers.models import Customer
from modules.push_log.models import ProductPushLog

from .auth import require_orchestrator_key, OrchestratorContext
from .idempotency import compute_payload_hash, check_idempotency
from .schemas import PushRequest, PushRequestAccepted, ErrorEnvelope
from .service import resolve_product_to_ingest, build_ops_client, compute_final_prices
from modules.ops_client.push import push_apparel_product

log = logging.getLogger("integration_gateway")
router = APIRouter(prefix="/api/integrations/v1", tags=["integration_gateway"])


@router.post("/push-requests", response_model=PushRequestAccepted, status_code=202)
async def create_push_request(
    body: PushRequest,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    ctx: OrchestratorContext = Depends(require_orchestrator_key),
    db: AsyncSession = Depends(get_db),
) -> PushRequestAccepted:
    payload_hash = compute_payload_hash(body.model_dump(mode="json"))

    # Idempotency check
    decision = await check_idempotency(
        db=db, key_id=ctx.key_id,
        idempotency_key=idempotency_key, payload_hash=payload_hash,
    )
    if decision.action == "conflict":
        raise HTTPException(409, "IDEMPOTENCY_CONFLICT: same key used with different payload")
    if decision.action == "return_existing":
        existing = await db.get(ProductPushLog, decision.existing_push_log_id)
        return PushRequestAccepted(
            push_log_id=existing.id,
            status=existing.status,
            customer_id=existing.customer_id,
            supplier_slug=existing.supplier_slug or body.source.supplier_slug,
            supplier_sku=existing.supplier_sku,
            ops_product_id=existing.ops_product_id,
            dry_run=body.dry_run,
            callback_status=existing.callback_status or "not_requested",
            created_at=existing.pushed_at,
        )

    # Resolve customer + product
    customer = await db.get(Customer, body.target.customer_id)
    if not customer:
        raise HTTPException(404, "UNKNOWN_REF: customer not found")
    if not body.product_ref.product_id:
        raise HTTPException(422, "PREFLIGHT_BLOCKER: product_ref.product_id required")
    product = await resolve_product_to_ingest(db, body.product_ref.product_id)
    if not product:
        raise HTTPException(404, "UNKNOWN_REF: product not found")

    # Insert push_log row
    push_log = ProductPushLog(
        id=uuid4(),
        product_id=body.product_ref.product_id,
        customer_id=body.target.customer_id,
        status="accepted",
        key_id=ctx.key_id,
        idempotency_key=idempotency_key,
        payload_hash=payload_hash,
        supplier_slug=body.source.supplier_slug,
        supplier_sku=product.supplier_sku,
        pushed_at=datetime.now(timezone.utc),
    )
    db.add(push_log)
    await db.commit()
    await db.refresh(push_log)

    # Execute push
    client = build_ops_client(customer, fake=body.dry_run)
    final_prices = await compute_final_prices(db, customer.id, product)
    result = await push_apparel_product(client=client, product=product, final_prices=final_prices)

    # Update push_log with terminal status
    push_log.status = "dry_run_pushed" if body.dry_run else result["status"]
    push_log.ops_product_id = str(result["ops_product_id"]) if result["ops_product_id"] else None
    push_log.step_results = result["step_results"]
    push_log.cleanup_targets = result["cleanup_targets"]
    push_log.error = result["error"]
    await db.commit()
    await db.refresh(push_log)

    return PushRequestAccepted(
        push_log_id=push_log.id,
        status=push_log.status,
        customer_id=customer.id,
        supplier_slug=body.source.supplier_slug,
        supplier_sku=product.supplier_sku,
        ops_product_id=push_log.ops_product_id,
        dry_run=body.dry_run,
        callback_status="not_requested",
        created_at=push_log.pushed_at,
    )
```

Add the import for `Header`:

```python
from fastapi import APIRouter, Depends, Header, HTTPException
```

- [ ] **Step 4: Register router in `main.py`**

```python
# backend/main.py — add to imports
from modules.integration_gateway.routes import router as integration_gateway_router

# In the router registrations block:
app.include_router(integration_gateway_router)
```

- [ ] **Step 5: Run, verify PASS**

```bash
cd backend && pytest tests/test_gateway_push_dry_run.py -v
```

- [ ] **Step 6: Commit**

```bash
git add backend/modules/integration_gateway/routes.py \
  backend/modules/integration_gateway/service.py \
  backend/tests/test_gateway_push_dry_run.py \
  backend/main.py
git commit -m "feat(gateway): POST /api/integrations/v1/push-requests

Full end-to-end push path: auth + idempotency + customer/product
resolve + push_log row creation + ops_client orchestrator dispatch +
terminal status update. dry_run uses FakeOpsClient (no real OPS calls).
Returns 202 + push_log_id + status."
```

---

### Task 16: GET /push-requests/{id}

**Files:**
- Modify: `backend/modules/integration_gateway/routes.py`
- Test: `backend/tests/test_gateway_push_dry_run.py`

- [ ] **Step 1: Add failing test**

```python
def test_get_push_request_returns_terminal_status(seeded_db, ...):
    # After dry_run push above, GET should return the same push_log_id with terminal status
    ...
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Add GET route**

```python
@router.get("/push-requests/{push_log_id}", response_model=PushRequestStatus)
async def get_push_request(
    push_log_id: UUID,
    ctx: OrchestratorContext = Depends(require_orchestrator_key),
    db: AsyncSession = Depends(get_db),
) -> PushRequestStatus:
    row = await db.get(ProductPushLog, push_log_id)
    if not row:
        raise HTTPException(404, "UNKNOWN_REF: push_log not found")
    return PushRequestStatus(
        push_log_id=row.id,
        status=row.status,
        customer_id=row.customer_id,
        supplier_slug=row.supplier_slug or "",
        supplier_sku=row.supplier_sku,
        ops_product_id=row.ops_product_id,
        error=row.error,
        step_results=row.step_results or [],
        cleanup_targets=row.cleanup_targets or [],
        callback_status=row.callback_status or "not_requested",
        callback_attempts=row.callback_attempts or 0,
        finished_at=row.pushed_at,
    )
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(gateway): GET /push-requests/{id} status poll"
```

---

### Task 17: POST /suppliers/{slug}/products (catalog upsert proxy)

**Files:**
- Modify: `backend/modules/integration_gateway/routes.py`
- Test: `backend/tests/test_gateway_products_ingest.py`

- [ ] **Step 1: Write failing test**

```python
def test_post_supplier_products_upserts_to_catalog(seeded_db, sanmar_supplier, monkeypatch):
    monkeypatch.setenv("INTEGRATION_KEY_oh-test", "raw-key-abc")
    client = TestClient(app)
    r = client.post(
        "/api/integrations/v1/suppliers/sanmar/products",
        headers={"X-Orchestrator-Key": "raw-key-abc", "Idempotency-Key": "sanmar-batch-001"},
        json={
            "mode": "upsert",
            "items": [{
                "supplier_sku": "PC61", "product_name": "Test", "product_type": "apparel",
                "variants": [{"part_id": "PC61-X", "size": "S", "color": "X", "sku": "PC61-X-S"}],
            }],
        },
    )
    assert r.status_code == 200
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Add route**

```python
@router.post("/suppliers/{supplier_slug}/products")
async def upsert_supplier_products(
    supplier_slug: str,
    body: dict,  # {mode: "upsert", items: ProductIngest[]}
    idempotency_key: str = Header(alias="Idempotency-Key"),
    ctx: OrchestratorContext = Depends(require_orchestrator_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delegate to existing catalog ingest persistence with snapshot=False."""
    from modules.catalog.persistence import persist_product
    from modules.catalog.schemas import ProductIngest
    from modules.suppliers.models import Supplier
    from sqlalchemy import select

    sup = (await db.execute(select(Supplier).where(Supplier.slug == supplier_slug))).scalar_one_or_none()
    if not sup:
        raise HTTPException(404, f"Supplier slug={supplier_slug} not found")
    items = [ProductIngest.model_validate(it) for it in body.get("items", [])]
    results = []
    for it in items:
        pid = await persist_product(db=db, supplier_id=sup.id, item=it, snapshot=False)
        results.append({"supplier_sku": it.supplier_sku, "product_id": str(pid)})
    await db.commit()
    return {"upserted": len(results), "items": results}
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(gateway): POST /suppliers/{slug}/products catalog upsert"
```

---

### Task 18: POST /master-options/ingest + POST /push-mappings + POST /connection-test + GET schema

**Files:**
- Modify: `backend/modules/integration_gateway/routes.py`
- Test: `backend/tests/test_gateway_aux_endpoints.py`

- [ ] **Step 1: Write failing tests for each**

```python
def test_master_options_ingest_proxies(...):
def test_push_mappings_upsert_proxies(...):
def test_connection_test_calls_real_probe(...):
def test_get_schema_returns_product_ingest_jsonschema(...):
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Add routes — each thin proxy**

```python
@router.post("/master-options/ingest")
async def master_options_ingest(
    body: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    ctx: OrchestratorContext = Depends(require_orchestrator_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from modules.master_options.ingest import _ingest_master_options
    return await _ingest_master_options(body=body, db=db)


@router.post("/push-mappings")
async def push_mappings_upsert(
    body: dict,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    ctx: OrchestratorContext = Depends(require_orchestrator_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    from modules.push_mappings.service import upsert_push_mapping
    return await upsert_push_mapping(db=db, **body)


@router.post("/customers/{customer_id}/ops/connection-test")
async def ops_connection_test(
    customer_id: UUID,
    ctx: OrchestratorContext = Depends(require_orchestrator_key),
    db: AsyncSession = Depends(get_db),
) -> dict:
    customer = await db.get(Customer, customer_id)
    if not customer:
        raise HTTPException(404, "UNKNOWN_REF: customer not found")
    client = build_ops_client(customer, fake=False)
    # Smallest possible authenticated call — ping mutation/query
    try:
        await client._get_token()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:300]}


@router.get("/suppliers/{supplier_slug}/schema")
async def get_supplier_schema(supplier_slug: str, ctx: OrchestratorContext = Depends(require_orchestrator_key)) -> dict:
    from modules.catalog.schemas import ProductIngest
    return ProductIngest.model_json_schema()
```

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat(gateway): aux endpoints (master-options/push-mappings/connection-test/schema)"
```

---

## M1.3 — Admin route rewire + markup collapse (2 tasks)

### Task 19: Rewire admin `/api/push/{cid}/{pid}` to gateway internally

**Files:**
- Modify: `backend/modules/ops_push/service.py`
- Modify: `backend/modules/ops_push/routes.py` (response shape preserved)
- Test: `backend/tests/test_gateway_admin_route_preserved.py`

- [ ] **Step 1: Write failing test (response shape preserved)**

```python
def test_admin_push_route_returns_preserved_shape(seeded_db, vg_customer, sanmar_pc61_product):
    client = TestClient(app)
    # ... login as vg_admin, set cookie ...
    r = client.post(f"/api/push/{vg_customer.id}/{sanmar_pc61_product.id}")
    assert r.status_code == 202
    body = r.json()
    # Must match old response shape exactly
    assert set(body.keys()) >= {"status", "push_log_id", "message", "payload"}
```

- [ ] **Step 2: Run, verify FAIL** (or PASS with old behavior; check after rewire test passes)

- [ ] **Step 3: Rewire `push_product` to call gateway internally**

Replace the body of `push_product()` in `service.py` to construct a gateway-style request and call the same `push_apparel_product` orchestrator + push_log path. Drop `trigger_n8n_push` call. Keep return-shape `{status, push_log_id, message, payload}`.

(Full implementation omitted from plan for brevity — engineer follows the same pattern as `create_push_request` but uses cookie auth + preserves output shape. Run the response-shape test to verify.)

- [ ] **Step 4: Run, verify PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "refactor(ops_push): admin route dispatches to ops_client; preserves response shape"
```

---

### Task 20: Collapse markup endpoints into single `/payload`

**Files:**
- Modify: `backend/modules/markup/routes.py:32-90`
- Test: `backend/tests/test_markup_payload_collapse.py`

- [ ] **Step 1: Write failing test**

```python
def test_payload_endpoint_returns_full_shape(...):
    # GET /api/markup-rules/{customer_id}/product/{product_id}/payload
    # returns {product, variants[final_price+base_price], options, sizes, images}
    # in a single response
    ...
```

- [ ] **Step 2: Run, verify FAIL**

- [ ] **Step 3: Merge `/payload` + `/ops-variants` + `/ops-options` into one**

(Engineer combines the 3 existing handlers in `markup/routes.py:32-90` into one. Removes the other two routes. Frontend / curl now hits one endpoint.)

- [ ] **Step 4: Run, verify PASS + check no stale callers**

```bash
grep -rn "/ops-variants\|/ops-options" backend/ frontend/src/ n8n-workflows/
```

Expected output: empty (or only deletions in M1.5).

- [ ] **Step 5: Commit**

```bash
git commit -am "refactor(markup): collapse /payload + /ops-variants + /ops-options into one"
```

---

## M1.4 — Frontend repoint (2 tasks)

### Task 21: Repoint "Push to OPS" button to gateway

**Files:**
- Modify: `frontend/src/components/products/push-row-action.tsx:53-56`
- Modify: `frontend/src/lib/api.ts` (add gateway helper)

- [ ] **Step 1: Add gateway helper to api.ts**

```typescript
// frontend/src/lib/api.ts — append
export const integrationGateway = {
  async pushRequest(opts: {
    customerId: string;
    productId: string;
    supplierSlug: string;
    dryRun?: boolean;
    idempotencyKey: string;
    orchestratorKey: string;
  }) {
    return api.post<{ push_log_id: string; status: string; dry_run: boolean }>(
      "/api/integrations/v1/push-requests",
      {
        target:      { customer_id: opts.customerId },
        source:      { supplier_slug: opts.supplierSlug },
        product_ref: { product_id: opts.productId },
        dry_run:     opts.dryRun ?? false,
      },
      {
        headers: {
          "X-Orchestrator-Key": opts.orchestratorKey,
          "Idempotency-Key": opts.idempotencyKey,
        },
      }
    );
  },

  async getPushStatus(pushLogId: string, orchestratorKey: string) {
    return api.get(`/api/integrations/v1/push-requests/${pushLogId}`, {
      headers: { "X-Orchestrator-Key": orchestratorKey },
    });
  },
};
```

- [ ] **Step 2: Modify `push-row-action.tsx:53-56`**

```typescript
// Replace the n8n trigger call with:
const idempotencyKey = `${product.id}-${customerId}-${Date.now()}`;
const orchestratorKey = process.env.NEXT_PUBLIC_ORCH_KEY ?? "";  // for admin path can also use cookie auth via /api/push/{cid}/{pid}
const result = await integrationGateway.pushRequest({
  customerId, productId: product.id, supplierSlug: supplier.slug,
  idempotencyKey, orchestratorKey,
});
toast.success(`Push queued (job ${result.push_log_id.slice(0, 8)})`);
// Start polling for terminal status using integrationGateway.getPushStatus
```

(Engineer writes the polling loop using `isTerminal` from `push-status.ts`.)

- [ ] **Step 3: Smoke-test in dev**

```bash
cd frontend && npm run dev
# Open /products, click "Push to OPS" on a product; verify modal updates from accepted → processing → pushed
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/products/push-row-action.tsx
git commit -m "feat(frontend): push-row-action repoints to integration gateway

Replaces direct n8n trigger with POST /api/integrations/v1/push-requests.
Polls GET endpoint until terminal status. Uses push-status.ts central
map to detect in-flight vs terminal states."
```

---

### Task 22: Apply status-map across 4 frontend components

**Files:**
- Modify: `frontend/src/components/SelectionBadge.tsx`
- Modify: `frontend/src/app/(admin)/customers/[id]/catalog/page.tsx`
- Modify: `frontend/src/app/(admin)/push-log/page.tsx`
- Modify: `frontend/src/components/products/push-history.tsx`

- [ ] **Step 1-N: For each file**

Replace hardcoded status maps with `getStatusMeta(status)`. Replace `s.status === "pushed"` with `isTerminal(s.status)` or specific check. Verify TypeScript still compiles.

- [ ] **Step N+1: Verify build**

```bash
cd frontend && npx tsc --noEmit
```

- [ ] **Step N+2: Commit**

```bash
git commit -am "refactor(frontend): apply push-status map across 4 components"
```

---

## M1.5 — Deletion of old n8n push (3 tasks; ONLY after M1.3 + M1.4 verified)

### Task 23: Delete `ops-push.json` + `ops-master-options-pull.json`

**Files:**
- Delete: `n8n-workflows/ops-push.json`
- Delete: `n8n-workflows/ops-master-options-pull.json`

- [ ] **Step 1: Verify zero references**

```bash
grep -rn "ops-push.json\|ops-master-options-pull.json\|N8N_PUSH_WEBHOOK_URL" backend/ frontend/src/
```

Expected: empty (or only the lines being deleted in next tasks).

- [ ] **Step 2: Delete files**

```bash
rm n8n-workflows/ops-push.json n8n-workflows/ops-master-options-pull.json
```

- [ ] **Step 3: Commit**

```bash
git rm n8n-workflows/ops-push.json n8n-workflows/ops-master-options-pull.json
git commit -m "chore(n8n): delete obsolete push + master-options workflows

ops-push.json and ops-master-options-pull.json are replaced by FastAPI
gateway endpoints. n8n stays for inbound supplier sync only."
```

---

### Task 24: Delete `trigger_n8n_push` + `N8N_PUSH_WEBHOOK_URL`

**Files:**
- Modify: `backend/modules/ops_push/service.py`
- Modify: `backend/main.py` (remove N8N_PUSH_WEBHOOK_URL from production-required env list if listed)

- [ ] **Step 1: Verify zero callers**

```bash
grep -rn "trigger_n8n_push\|N8N_PUSH_WEBHOOK_URL" backend/
```

Expected: only the function definition + the env var read inside it.

- [ ] **Step 2: Delete the function and its caller invocation**

(Engineer removes the function body and any remaining caller. Confirms `push_product` now calls only `push_apparel_product` from ops_client.)

- [ ] **Step 3: Run tests, verify still PASS**

```bash
cd backend && pytest tests/test_ops_push*.py tests/test_gateway*.py -v
```

- [ ] **Step 4: Commit**

```bash
git commit -am "chore(ops_push): remove trigger_n8n_push + N8N_PUSH_WEBHOOK_URL

OPS push now flows entirely through FastAPI ops_client. No n8n in the
push path."
```

---

### Task 25: Shrink `ops_push/merge.py` (or delete)

**Files:**
- Modify: `backend/modules/ops_push/merge.py`

- [ ] **Step 1: Audit what still uses merge.py**

```bash
grep -rn "merge_product_with_decorations\|ops_push.merge" backend/
```

- [ ] **Step 2: If no remaining callers — delete the file**

```bash
git rm backend/modules/ops_push/merge.py
```

If any callers remain, shrink to hub-domain merge only (drop OPS field mapping — that lives in ops_client now).

- [ ] **Step 3: Run full backend tests**

```bash
cd backend && pytest -x
```

- [ ] **Step 4: Commit**

```bash
git commit -m "chore(ops_push): remove (or shrink) merge.py

OPS-shaped payload building now lives in ops_client. merge.py was the
last n8n-coupled artifact in the push path."
```

---

## Self-review checklist

- [ ] Every task has at least: failing test → implementation → passing test → commit
- [ ] No placeholders, no "implement later"
- [ ] Type/method names consistent across tasks (`push_apparel_product`, `OpsResult`, `OrchestratorContext`)
- [ ] Spec sections all covered: 9 endpoints, field mapping, ID threading, file changes, n8n role, migration phases, tests
- [ ] M1.5 deletion strictly after M1.3 + M1.4 verified (Task 19 + 21 + 22 must PASS before Task 23+)
- [ ] No deployment scope (ECS/SQS/CloudFront) — deferred per spec
- [ ] M1.6 decoration push out of scope — handle in separate plan when first decoration product onboards

## Out of scope (handle separately)

- M1.6 — option chain mutations (setAdditionalOption + setAdditionalOptionAttributes + setProductsAttributePrice) — deferred until first decoration product
- M2 — admin UI for integration_keys (per Rev 3 spec section "Database changes")
- M3-M5 of Rev 3 spec — happen after M1 stabilizes
- 4Over, S&S adapters — no creds yet
- AWS ECS / SQS / CloudFront
- SECRET_KEY rotation automation
- `variant_axes` table refactor

---

**End of plan. Total tasks: 25. Estimated effort: ~12-15 senior dev-days.**
