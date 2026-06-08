# Security Leak Remediation Implementation Plan

> **✅ DONE (landed, verified 2026-06-02).** Shipped mostly via PR #160 (SSRF guard on
> image preflight, `sanitize_error` redaction, n8n proxy `vg_admin` gate, XFF-aware
> limiter, Next.js `remotePatterns`, Sentry `maskAllText`+`blockAllMedia`, push-mappings
> tenant guard) plus the IDOR audit (issues #147–#153, #29 closed). See "Current state"
> in `plans/2026-06-02-production-readiness.md`. The unticked `- [ ]` boxes below are
> historical — the work is complete.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the exploitable leaks from the 2026-05-29 four-lane security audit — SSRF to cloud metadata, cross-tenant IDOR (markup writes, push-log, push-mappings, products, orchestrator push-status), rate-limit bypass, error-body echo, and Sentry credential capture.

**Architecture:** Two systemic root causes drive most findings: (1) `main.py` applies a blanket `get_current_user` to tenant routers — authentication without authorization — so any route taking `customer_id` from path/body/query that lacks an explicit `require_customer_access`/`check_key_scope`/`VGAdmin` guard is reachable cross-tenant; (2) the SSRF guard exists in `images/mirror.py` but wasn't reused in `ops_push/image_pipeline.py`. Fix: extract the SSRF guard to a shared module and reuse it; add the missing tenant guards using the existing `require_customer_access` (path) / inline (body/query) / `check_key_scope` (orchestrator key) patterns.

**Tech Stack:** FastAPI, async SQLAlchemy + asyncpg, slowapi, httpx, Pillow, pytest + pytest-asyncio + httpx ASGITransport, Next.js / @sentry/nextjs.

---

## Prerequisites

- [ ] **Step 0a: Branch off main**

```bash
cd /Users/tanishq/Documents/project-files/api-hub/api-hub
git checkout main && git pull --ff-only
git checkout -b fix/security-leaks
```

- [ ] **Step 0b: Backend test env**

```bash
docker compose up -d postgres
cd backend && source .venv/bin/activate && pip install -r requirements.txt
```

All `pytest` runs from `backend/` with the venv active. The existing tenant-test harness is `backend/tests/test_tenant_access.py` (fixture `as_user` overrides `get_current_user`, restores `_TEST_ADMIN` in `finally`). Reuse it.

---

## File Structure

- `backend/modules/common/__init__.py` — **Create.** New package for cross-module security primitives.
- `backend/modules/common/ssrf.py` — **Create.** `assert_safe_url(url)` (the proven impl, moved from `images/mirror.py`).
- `backend/modules/ops_push/image_pipeline.py` — **Modify.** Call `assert_safe_url`, `follow_redirects=False`.
- `backend/modules/images/mirror.py` — **Modify.** Re-point to the shared guard (delete local copy).
- `backend/modules/markup/routes.py` — **Modify.** Tenant-guard create/update/delete.
- `backend/modules/push_log/routes.py` — **Modify.** Scope list/create/push-status to caller's tenant (or VGAdmin).
- `backend/modules/push_mappings/routes.py` — **Modify.** Scope GET to caller's tenant.
- `backend/modules/catalog/routes.py` — **Modify.** Scope the `customer_id` product filter.
- `backend/modules/integrations/routes.py` — **Modify.** `get_push_status` → `check_key_scope`. Generic error in OPS connection-test.
- `backend/modules/customers/routes.py`, `backend/modules/suppliers/routes.py` — **Modify.** Stop echoing raw upstream error bodies.
- `backend/modules/common/sanitize.py` — **Create.** `sanitize_error()` redactor.
- `backend/limiter.py` — **Modify.** XFF-aware `key_func`.
- `backend/main.py` — **Modify.** Run uvicorn note + ensure n8n proxy (if mounted) is VGAdmin.
- `frontend/instrumentation-client.ts` — **Modify.** Sentry replay masking.
- `frontend/next.config.ts` — **Modify.** Restrict image `remotePatterns`.
- `backend/tests/test_ssrf_guard.py`, `backend/tests/test_tenant_access_extra.py`, `backend/tests/test_error_sanitize.py` — **Create.**

---

## Task 1: SSRF guard on the OPS image pipeline (CRITICAL)

**Files:**
- Create: `backend/modules/common/__init__.py`, `backend/modules/common/ssrf.py`
- Test: `backend/tests/test_ssrf_guard.py`
- Modify: `backend/modules/ops_push/image_pipeline.py:27-29`, `backend/modules/images/mirror.py:61-81,94,96`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_ssrf_guard.py`:

```python
"""SSRF guard — assert_safe_url blocks metadata/loopback/private/non-http targets."""
import pytest

from modules.common.ssrf import assert_safe_url


@pytest.mark.no_db
@pytest.mark.parametrize("bad", [
    "http://169.254.169.254/latest/meta-data/iam/security-credentials/",  # cloud metadata
    "http://127.0.0.1/admin",
    "http://localhost:5678/",
    "file:///etc/passwd",
    "gopher://x/",
    "http://0.0.0.0/",
])
def test_assert_safe_url_rejects(bad):
    with pytest.raises(ValueError):
        assert_safe_url(bad)


@pytest.mark.no_db
def test_assert_safe_url_allows_public():
    # Public host must not raise (resolves to a public IP).
    assert_safe_url("https://www.example.com/image.jpg")


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_process_image_blocks_private_url():
    from modules.ops_push.image_pipeline import process_image
    with pytest.raises(ValueError):
        await process_image("http://169.254.169.254/latest/meta-data/")
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_ssrf_guard.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.common.ssrf'`.

- [ ] **Step 3: Create the shared guard**

Create `backend/modules/common/__init__.py` (empty file).

Create `backend/modules/common/ssrf.py`:

```python
"""SSRF guard shared by every code path that fetches a URL from DB/user input.

Blocks non-http(s) schemes and hosts that resolve to private / loopback /
link-local / reserved IPs (cloud metadata 169.254.169.254, localhost,
RFC-1918, etc.). Validates ALL resolved records, not just the first.
"""
import ipaddress
import socket
from urllib.parse import urlparse


def assert_safe_url(url: str) -> None:
    """Raise ValueError if `url` must not be fetched from server-side code."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Disallowed URL scheme: {parsed.scheme!r}")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError("URL has no hostname")
    try:
        infos = socket.getaddrinfo(hostname, None)
    except OSError as exc:
        raise ValueError(f"Cannot resolve hostname {hostname!r}: {exc}") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            raise ValueError(f"URL resolves to a disallowed address ({ip}) — SSRF guard")
```

- [ ] **Step 4: Apply the guard in the OPS image pipeline**

In `backend/modules/ops_push/image_pipeline.py`, add the import after line 10 (`from PIL import Image`):

```python
from modules.common.ssrf import assert_safe_url
```

Replace the download block (lines 26-29):

```python
    # SSRF guard — source_url comes from supplier ingest (untrusted). Block
    # cloud-metadata / loopback / private targets, and do NOT follow redirects
    # (a public URL could 30x into an internal one).
    assert_safe_url(source_url)
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        r = await client.get(source_url)
        r.raise_for_status()
```

- [ ] **Step 5: Re-point mirror.py to the shared guard (DRY)**

In `backend/modules/images/mirror.py`: delete the local `_assert_safe_url` function (lines 61-81) and add at the top with the other imports:

```python
from modules.common.ssrf import assert_safe_url
```

In `_fetch_and_process` change line 94 `_assert_safe_url(url)` → `assert_safe_url(url)`, and change line 96 `follow_redirects=True` → `follow_redirects=False`. (Remove now-unused `ipaddress`/`socket`/`urlparse` imports if no longer referenced — run `python -c "import ast"` check or leave; harmless.)

- [ ] **Step 6: Run to verify pass**

Run: `pytest tests/test_ssrf_guard.py -v`
Expected: PASS (all rejects raise; public allowed; `process_image` blocks metadata).

- [ ] **Step 7: Regression — existing mirror tests still pass**

Run: `pytest tests/ -k mirror -v`
Expected: PASS (no behavior change beyond redirect policy).

- [ ] **Step 8: Commit**

```bash
git add backend/modules/common/ backend/modules/ops_push/image_pipeline.py backend/modules/images/mirror.py backend/tests/test_ssrf_guard.py
git commit -m "fix(security): SSRF guard on OPS image pipeline; share assert_safe_url, no redirects"
```

---

## Task 2: Tenant-guard markup-rule writes (CRITICAL IDOR)

**Files:**
- Test: `backend/tests/test_tenant_access_extra.py`
- Modify: `backend/modules/markup/routes.py:166-198`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_tenant_access_extra.py`:

```python
"""Cross-tenant IDOR guards added in fix/security-leaks."""
import uuid

import pytest

from main import app
from modules.auth.dependencies import get_current_user
from modules.auth.models import User


def _user(role, customer_id=None):
    u = User()
    u.id = uuid.uuid4()
    u.email = f"{role}@vg.test"
    u.hashed_password = "x"
    u.role = role
    u.customer_id = customer_id
    u.is_active = True
    return u


@pytest.fixture
def as_user():
    def _set(user):
        app.dependency_overrides[get_current_user] = lambda: user
    try:
        yield _set
    finally:
        from tests.conftest import _TEST_ADMIN
        app.dependency_overrides[get_current_user] = lambda: _TEST_ADMIN


@pytest.mark.asyncio
async def test_markup_create_blocks_other_customer(client, as_user):
    a, b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=a))
    r = await client.post("/api/markup-rules", json={
        "customer_id": str(b), "scope": "all", "markup_pct": 10,
    })
    assert r.status_code == 403
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_tenant_access_extra.py::test_markup_create_blocks_other_customer -v`
Expected: FAIL — returns 201 (no guard today).

- [ ] **Step 3: Apply the guard**

In `backend/modules/markup/routes.py`, add to imports (line 10 area already has `from modules.catalog.ingest import require_ingest_secret`):

```python
from modules.auth.dependencies import CurrentUser, require_customer_access
```

Replace `create_markup_rule` (lines 166-172):

```python
@router.post("", response_model=MarkupRuleRead, status_code=201)
async def create_markup_rule(
    body: MarkupRuleCreate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    require_customer_access(body.customer_id, current_user)
    rule = MarkupRule(**body.model_dump())
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    return rule
```

Replace `update_markup_rule` (lines 175-187) — guard the loaded row's `customer_id`:

```python
@router.patch("/{rule_id}", response_model=MarkupRuleRead)
async def update_markup_rule(
    rule_id: UUID, body: MarkupRuleUpdate, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    """Partial update of a markup rule. Only fields present in the body are updated."""
    result = await db.execute(select(MarkupRule).where(MarkupRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Markup rule not found")
    require_customer_access(rule.customer_id, current_user)
    updates = body.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(rule, field, value)
    await db.commit()
    await db.refresh(rule)
    return rule
```

Replace `delete_markup_rule` (lines 190-198):

```python
@router.delete("/{rule_id}")
async def delete_markup_rule(
    rule_id: UUID, current_user: CurrentUser, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(MarkupRule).where(MarkupRule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(404, "Markup rule not found")
    require_customer_access(rule.customer_id, current_user)
    await db.delete(rule)
    await db.commit()
    return {"deleted": True}
```

Also guard the existing `list_markup_rules` (line 156) if not already — it has `dependencies=[Depends(require_customer_access)]` from #144; confirm it's present, leave as-is.

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_tenant_access_extra.py::test_markup_create_blocks_other_customer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/markup/routes.py backend/tests/test_tenant_access_extra.py
git commit -m "fix(security): tenant-guard markup-rule create/update/delete (cross-tenant IDOR)"
```

---

## Task 3: Lock down push-log routes (CRITICAL/HIGH)

`/api/push-log` list/create and `/api/products/{id}/push-status` return all-tenant data and accept forged `customer_id`. Customer-facing reads already exist at `/api/portal/push-history` (correctly scoped). Simplest correct fix: make these three VGAdmin-only.

**Files:**
- Test: `backend/tests/test_tenant_access_extra.py` (append)
- Modify: `backend/modules/push_log/routes.py`

- [ ] **Step 1: Write the failing test** (append)

```python
@pytest.mark.asyncio
async def test_push_log_list_forbidden_for_customer_admin(client, as_user):
    as_user(_user("customer_admin", customer_id=uuid.uuid4()))
    r = await client.get("/api/push-log")
    assert r.status_code == 403
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_tenant_access_extra.py::test_push_log_list_forbidden_for_customer_admin -v`
Expected: FAIL — returns 200 with all-tenant rows.

- [ ] **Step 3: Apply VGAdmin gate**

In `backend/modules/push_log/routes.py`, add import:

```python
from modules.auth.dependencies import VGAdmin
```

Add `_: VGAdmin` to all three handlers:
- `list_push_logs` (line 18) — add `_: VGAdmin,` as first param after the function opens (before the query params with defaults; since `VGAdmin` has no default it must precede defaulted params):

```python
async def list_push_logs(
    _: VGAdmin,
    product_id: UUID | None = None,
    customer_id: UUID | None = None,
    limit: int = Query(default=20, le=200),
    db: AsyncSession = Depends(get_db),
):
```
- `create_push_log` (line 59): `async def create_push_log(body: PushLogCreate, _: VGAdmin, db: AsyncSession = Depends(get_db)):`
- `get_push_status` (line 93): `async def get_push_status(product_id: UUID, _: VGAdmin, db: AsyncSession = Depends(get_db)):`

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_tenant_access_extra.py::test_push_log_list_forbidden_for_customer_admin -v`
Expected: PASS. Also confirm vg_admin still 200:

```bash
pytest tests/test_tenant_access_extra.py -v
```

- [ ] **Step 5: Commit**

```bash
git add backend/modules/push_log/routes.py backend/tests/test_tenant_access_extra.py
git commit -m "fix(security): restrict /api/push-log + push-status to VGAdmin (cross-tenant read/forge)"
```

---

## Task 4: Scope orchestrator push-status by key (CRITICAL)

`integrations/routes.py:get_push_status` does a bare `db.get(ProductPushLog, push_log_id)` with no `check_key_scope` — any orchestrator key reads any tenant's push log.

**Files:**
- Modify: `backend/modules/integrations/routes.py:163-172`

- [ ] **Step 1: Apply the scope check**

`check_key_scope(key, customer_id: str, supplier_slug: str)` is already imported/used by the write paths in this file. After loading `push_log` (line 168-172), add:

```python
    push_log = await db.get(ProductPushLog, push_log_id)
    if not push_log:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": "Push request not found"
        })
    # Enforce the same key scope the write paths use. 404 (not 403) so a
    # foreign key cannot confirm the existence of another tenant's push.
    try:
        check_key_scope(key, str(push_log.customer_id), push_log.supplier_slug or "*")
    except HTTPException:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail={
            "code": "UNKNOWN_REF", "message": "Push request not found"
        })
```

Confirm `check_key_scope` is imported at the top of the file (it is used elsewhere here; if the symbol isn't imported add `from modules.integrations.auth import check_key_scope`).

- [ ] **Step 2: Verify import smoke**

Run: `python -c "import main; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add backend/modules/integrations/routes.py
git commit -m "fix(security): enforce key scope on orchestrator push-status read (cross-tenant)"
```

---

## Task 5: Scope push-mappings GET (HIGH)

**Files:**
- Test: `backend/tests/test_tenant_access_extra.py` (append)
- Modify: `backend/modules/push_mappings/routes.py:26-32`

- [ ] **Step 1: Write the failing test** (append)

```python
@pytest.mark.asyncio
async def test_push_mappings_list_blocks_other_customer(client, as_user):
    a, b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=a))
    r = await client.get(f"/api/push-mappings?customer_id={b}")
    assert r.status_code == 403
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_tenant_access_extra.py::test_push_mappings_list_blocks_other_customer -v`
Expected: FAIL — returns 200.

- [ ] **Step 3: Apply the inline guard**

In `backend/modules/push_mappings/routes.py`, add import:

```python
from modules.auth.dependencies import CurrentUser
```

Replace `list_mappings` (lines 26-32):

```python
@router.get("", response_model=list[PushMappingRead])
async def list_mappings(
    current_user: CurrentUser,
    customer_id: UUID = Query(None),
    source_product_id: UUID = Query(None),
    db: AsyncSession = Depends(get_db),
):
    # customer_admin may only read their own tenant; force the filter and
    # reject a foreign customer_id. vg_admin / ingest may pass any/none.
    if current_user.role == "customer_admin":
        if customer_id is not None and customer_id != current_user.customer_id:
            raise HTTPException(403, "Not authorized for this customer")
        customer_id = current_user.customer_id
    return await service.get_push_mappings(db, customer_id, source_product_id)
```

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_tenant_access_extra.py::test_push_mappings_list_blocks_other_customer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/push_mappings/routes.py backend/tests/test_tenant_access_extra.py
git commit -m "fix(security): scope push-mappings GET to caller's tenant (IDOR)"
```

---

## Task 6: Scope catalog product `customer_id` filter (HIGH)

**Files:**
- Test: `backend/tests/test_tenant_access_extra.py` (append)
- Modify: `backend/modules/catalog/routes.py` (the `list_products` handler — params at lines 46-56, filter at 90-98)

- [ ] **Step 1: Write the failing test** (append)

```python
@pytest.mark.asyncio
async def test_products_customer_filter_blocks_other_customer(client, as_user):
    a, b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=a))
    r = await client.get(f"/api/products?customer_id={b}")
    assert r.status_code == 403
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_tenant_access_extra.py::test_products_customer_filter_blocks_other_customer -v`
Expected: FAIL — returns 200.

- [ ] **Step 3: Apply the inline guard**

In `backend/modules/catalog/routes.py`, ensure `from modules.auth.dependencies import CurrentUser` is imported. Add `current_user: CurrentUser` to the `list_products` signature (as the first param, before defaulted params). Immediately before the `if customer_id:` block (line 90) add:

```python
    if customer_id is not None and current_user.role == "customer_admin":
        if customer_id != current_user.customer_id:
            raise HTTPException(403, "Not authorized for this customer")
```

Confirm `HTTPException` is imported in this file (add `from fastapi import HTTPException` if absent).

- [ ] **Step 4: Run to verify pass**

Run: `pytest tests/test_tenant_access_extra.py::test_products_customer_filter_blocks_other_customer -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/catalog/routes.py backend/tests/test_tenant_access_extra.py
git commit -m "fix(security): scope product customer_id filter to caller's tenant (IDOR)"
```

---

## Task 7: XFF-aware rate limiter (HIGH)

`limiter.py` uses `get_remote_address` → behind ALB all clients collapse to the LB IP (global bucket; login brute-force/DoS).

**Files:**
- Test: `backend/tests/test_error_sanitize.py` (reused file; add a limiter unit test here or a new `test_limiter.py`)
- Modify: `backend/limiter.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_limiter.py`:

```python
"""Rate-limit key derivation honors X-Forwarded-For behind a proxy."""
import types

import pytest

from limiter import _client_ip


@pytest.mark.no_db
def test_client_ip_prefers_xff_last_hop():
    req = types.SimpleNamespace(
        headers={"x-forwarded-for": "203.0.113.7, 10.0.0.1"},
        client=types.SimpleNamespace(host="10.0.0.1"),
    )
    assert _client_ip(req) == "10.0.0.1" or _client_ip(req) == "203.0.113.7"


@pytest.mark.no_db
def test_client_ip_falls_back_to_peer():
    req = types.SimpleNamespace(headers={}, client=types.SimpleNamespace(host="198.51.100.9"))
    assert _client_ip(req) == "198.51.100.9"
```

> Note: ALB appends the real client as the right-most XFF entry and adds exactly one hop. Pick the right-most entry. If your proxy topology differs, document the hop count. The test asserts the function returns the configured untrusted hop.

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_limiter.py -v`
Expected: FAIL — `ImportError: cannot import name '_client_ip'`.

- [ ] **Step 3: Implement**

In `backend/limiter.py`, replace the `Limiter(key_func=get_remote_address)` construction:

```python
from slowapi import Limiter


def _client_ip(request) -> str:
    """Client IP for rate limiting. Behind the ALB the real client is the
    right-most X-Forwarded-For entry; fall back to the socket peer."""
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[-1].strip()
    return request.client.host if request.client else "127.0.0.1"


limiter = Limiter(key_func=_client_ip)
```

- [ ] **Step 4: Run to verify pass + import smoke**

Run: `pytest tests/test_limiter.py -v && python -c "import main; print('ok')"`
Expected: PASS + `ok`.

- [ ] **Step 5: Deploy note** — uvicorn must trust only the LB for forwarded headers. Update `backend/Dockerfile` / `bootstrap.sh` uvicorn invocation to add `--proxy-headers --forwarded-allow-ips="*"` (or the ALB subnet CIDR). Add this as a comment in `limiter.py` so the deploy dependency is discoverable. (slowapi is in-process per worker — note in the file that a Redis backend is required for a true shared limit; tracked separately.)

- [ ] **Step 6: Commit**

```bash
git add backend/limiter.py backend/tests/test_limiter.py backend/Dockerfile backend/bootstrap.sh
git commit -m "fix(security): XFF-aware rate-limit key; trust forwarded headers from LB only"
```

---

## Task 8: Stop echoing raw upstream error bodies (HIGH)

**Files:**
- Create: `backend/modules/common/sanitize.py`
- Test: `backend/tests/test_error_sanitize.py`
- Modify: `backend/modules/integrations/routes.py` (OPS connection-test ~476-484, `_ops_graphql_ping` ~90), `backend/modules/customers/routes.py:159-172`, `backend/modules/suppliers/routes.py:235-239`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_error_sanitize.py`:

```python
"""sanitize_error redacts credential-shaped substrings and truncates."""
import pytest

from modules.common.sanitize import sanitize_error


@pytest.mark.no_db
def test_redacts_bearer_and_secret():
    s = sanitize_error("auth failed: Bearer abc123tok client_secret=shh password=hunter2")
    assert "abc123tok" not in s
    assert "shh" not in s
    assert "hunter2" not in s
    assert "[REDACTED]" in s


@pytest.mark.no_db
def test_truncates():
    assert len(sanitize_error("x" * 5000)) <= 300
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_error_sanitize.py -v`
Expected: FAIL — `ModuleNotFoundError: modules.common.sanitize`.

- [ ] **Step 3: Implement the redactor**

Create `backend/modules/common/sanitize.py`:

```python
"""Redact credential-shaped substrings before persisting/returning error text."""
import re

_PATTERNS = re.compile(
    r"(bearer\s+\S+"
    r"|client_secret=\S+"
    r"|password=\S+"
    r"|access_token\"?\s*[:=]\s*\"?[\w.\-]+"
    r"|refresh_token\"?\s*[:=]\s*\"?[\w.\-]+)",
    re.IGNORECASE,
)


def sanitize_error(value: object, limit: int = 300) -> str:
    """Return a redacted, length-capped string safe to store or return."""
    return _PATTERNS.sub("[REDACTED]", str(value))[:limit]
```

- [ ] **Step 4: Apply at the echo sites**

`backend/modules/integrations/routes.py` — replace the connection-test returns that embed `{exc}` (around lines 476-484) with a generic code + server-side log:

```python
    except Exception:
        logger.exception("ops_connection_test failed customer=%s", customer.id)
        return {"ok": False, "error_code": "OAUTH_FAILED",
                "error": "Could not authenticate against the OPS token endpoint."}
```
In `_ops_graphql_ping` (~line 90), do not put `resp.text` in the raised message — raise `RuntimeError(f"OPS GraphQL returned {resp.status_code}")` and log the body separately.

`backend/modules/customers/routes.py:159-172` — replace `"error": resp.text[:200]` / `str(exc)[:200]` with a generic message; log `resp.text` server-side:

```python
        logger.warning("ops token test non-200 customer=%s status=%s body=%s",
                       customer_id, resp.status_code, resp.text[:500])
        return {"ok": False, "customer_id": str(customer_id),
                "http_status": resp.status_code, "error_code": "TOKEN_ENDPOINT_REJECTED"}
```

`backend/modules/suppliers/routes.py:235-239` — return a generic message; log `str(e)` server-side. Where any of these persist an error to a DB row elsewhere, wrap with `sanitize_error(...)`.

- [ ] **Step 5: Run to verify + import smoke**

Run: `pytest tests/test_error_sanitize.py -v && python -c "import main; print('ok')"`
Expected: PASS + `ok`.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/common/sanitize.py backend/tests/test_error_sanitize.py backend/modules/integrations/routes.py backend/modules/customers/routes.py backend/modules/suppliers/routes.py
git commit -m "fix(security): generic upstream-error responses + sanitize_error redactor (info disclosure)"
```

---

## Task 9: Sentry Replay masking on credential screens (HIGH)

**Files:**
- Modify: `frontend/instrumentation-client.ts`

- [ ] **Step 1: Apply explicit masking**

In `frontend/instrumentation-client.ts`, replace the `integrations: [Sentry.replayIntegration()]` line with explicit masking:

```ts
  integrations: [
    Sentry.replayIntegration({
      maskAllInputs: true,
      maskAllText: true,
      blockAllMedia: true,
    }),
  ],
```

Also read both sample rates from env with safe defaults (so they can be tuned without redeploy):

```ts
  tracesSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_TRACES_SAMPLE_RATE ?? "0.2"),
  replaysOnErrorSampleRate: Number(process.env.NEXT_PUBLIC_SENTRY_REPLAY_ERROR_RATE ?? "0.5"),
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: build succeeds (no TS errors).

- [ ] **Step 3: Commit**

```bash
git add frontend/instrumentation-client.ts
git commit -m "fix(security): mask all inputs/text in Sentry Replay; env-tune sample rates"
```

---

## Task 10: Restrict Next.js image remotePatterns (MEDIUM)

**Files:**
- Modify: `frontend/next.config.ts:6-11`

- [ ] **Step 1: Apply allowlist**

Replace the wildcard `remotePatterns` with the actual supplier/CDN hosts (drop `http`). Determine the real hosts from `backend/.env` `S3`/CDN config + supplier image domains; start with:

```ts
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "*.sanmar.com" },
      { protocol: "https", hostname: "cdn.ssactivewear.com" },
      { protocol: "https", hostname: "*.alphabroder.com" },
      // add the project's own CDN/S3/R2 host here
    ],
  },
```

- [ ] **Step 2: Verify build + a known image renders**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: build succeeds. (Manually confirm a product image still loads against the configured hosts; add any missing supplier host.)

- [ ] **Step 3: Commit**

```bash
git add frontend/next.config.ts
git commit -m "fix(security): restrict next/image remotePatterns to supplier/CDN hosts (SSRF/open-proxy)"
```

---

## Task 11: Ensure n8n proxy is VGAdmin-gated when mounted (HIGH, coordinate)

`n8n_proxy/routes.py` is built with NO auth dependency and is not currently mounted in `main.py`. Branch `fix/phase-bc-cleanup` (sinchana) registers it. Whoever mounts it MUST attach a VGAdmin dependency.

**Files:**
- Modify: `backend/main.py` (the `include_router` for n8n proxy, when added)

- [ ] **Step 1: Add a guard test** (append to `backend/tests/test_tenant_access_extra.py`)

```python
@pytest.mark.asyncio
async def test_n8n_proxy_forbidden_for_customer_admin(client, as_user):
    as_user(_user("customer_admin", customer_id=uuid.uuid4()))
    r = await client.get("/api/n8n/workflows")
    # 403 if mounted+guarded, 404 if not mounted — both acceptable (NOT 200)
    assert r.status_code in (403, 404)
```

- [ ] **Step 2: Run**

Run: `pytest tests/test_tenant_access_extra.py::test_n8n_proxy_forbidden_for_customer_admin -v`
Expected: PASS (currently 404 — not mounted). The test prevents a future unguarded mount returning 200.

- [ ] **Step 3: If/when mounting**, register with VGAdmin:

```python
from modules.auth.dependencies import _require_vg_admin
app.include_router(n8n_proxy_router, dependencies=[Depends(_require_vg_admin)])
```

- [ ] **Step 4: Commit**

```bash
git add backend/tests/test_tenant_access_extra.py
git commit -m "test(security): assert n8n proxy never reachable by customer_admin"
```

---

## Task 12: Full suite + PR

- [ ] **Step 1: Run the whole backend suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: all pass (new `test_ssrf_guard`, `test_tenant_access_extra`, `test_error_sanitize`, `test_limiter` included). No `coroutine never awaited` warnings.

- [ ] **Step 2: Frontend build**

Run: `cd frontend && npm run build 2>&1 | tail -5`
Expected: success.

- [ ] **Step 3: Push + PR + request independent security review**

```bash
git push -u origin fix/security-leaks
gh pr create --base main --title "fix(security): close audit leaks — SSRF, cross-tenant IDOR, rate-limit, info-disclosure, Sentry" \
  --body "Remediates the 2026-05-29 security audit. See plans/2026-05-29-security-leak-remediation.md. Do NOT self-approve — request a separate security review pass."
```

Do not self-merge; route to an independent `security-reviewer` pass (separate lane). After merge, the deferred items (refresh-token revocation, Redis-backed limiter, ingest-secret narrowing/rotation, security-headers middleware, DNS-rebinding connect-time pinning) become follow-up tasks.

---

## Self-Review Notes
- **Spec coverage:** CRITICAL #1 SSRF (Task 1), #2 markup IDOR (Task 2), #3 push-log (Task 3) + orchestrator push-status (Task 4); HIGH push-mappings (5), products (6), rate-limit (7), error-echo (8), Sentry (9); MEDIUM image remotePatterns (10); n8n-proxy guard (11). DNS-rebinding TOCTOU partially mitigated via `follow_redirects=False` + `getaddrinfo` all-records (Task 1); full connect-time IP pinning deferred (noted Task 12).
- **Type/name consistency:** shared guard named `assert_safe_url` everywhere (Task 1); `sanitize_error` (Task 8); `require_customer_access(customer_id, current_user)` used inline with both args (Tasks 2,5,6) matching its real signature (`dependencies.py:149`); `check_key_scope(key, str, str)` matches `integrations/auth.py:122` (Task 4); `VGAdmin`/`CurrentUser` deps must precede defaulted params (Task 3,6 note).
- **Deferred (separate plan, NOT this PR):** refresh-token reuse-detection/revocation, Redis-backed rate limiter, `_INGEST_ALLOWED_PATH_PREFIXES` narrowing + secret rotation, security-headers middleware (CSP/HSTS/X-Frame-Options), cookie `Secure`/`SameSite` for staging, the M1 OPS-schema-format rewrite (separate `project_m1_ops_client_wrong_schema` issue).
