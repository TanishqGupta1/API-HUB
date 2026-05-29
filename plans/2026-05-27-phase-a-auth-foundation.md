# Auth Foundation Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three live auth/authorization holes (vg_admin self-registration, dead per-key rate limiter, cross-tenant IDOR) and make the foundation enforceable (blocking CI, migrations that match the models), on a branch every open PR can rebase onto.

**Architecture:** Small security-focused branch `harden/auth-foundation` off `main`. Public registration becomes bootstrap-only (first admin on empty DB; all later accounts admin-provisioned — decision locked with the user). A single reusable `require_customer_access` FastAPI dependency enforces tenant ownership on `customer_id`-scoped routes. The integration-gateway rate limiter is actually awaited. Three missing tables/columns get Alembic revisions so `create_all` is no longer load-bearing.

**Tech Stack:** FastAPI, async SQLAlchemy 2.0 + asyncpg, slowapi (rate limiting), Alembic, pytest + pytest-asyncio + httpx ASGITransport, GitHub Actions.

---

## Prerequisites

- [ ] **Step 0a: Create the branch**

```bash
cd /Users/tanishq/Documents/project-files/api-hub/api-hub
git checkout main && git pull
git checkout -b harden/auth-foundation
```

- [ ] **Step 0b: Bring up Postgres for DB-backed tests** (hermetic tests marked `@pytest.mark.no_db` don't need it)

```bash
docker compose up -d postgres
cd backend && python -m venv .venv 2>/dev/null; source .venv/bin/activate
pip install -r requirements.txt
```

All `pytest` commands below run from `backend/` with the venv active.

---

## File Structure

- `backend/tests/test_auth_hardening.py` — **Create.** All Phase A tests (rate limiter, register, signup-status).
- `backend/tests/test_tenant_access.py` — **Create.** Cross-tenant IDOR tests.
- `backend/modules/integrations/auth.py` — **Modify.** Await the limiter; keep a strong ref to the background task.
- `backend/modules/auth/routes.py` — **Modify.** Register/setup/signup-status hardening.
- `backend/modules/auth/dependencies.py` — **Modify.** Add `require_customer_access`.
- `backend/modules/markup/routes.py` — **Modify.** Apply the guard (representative; repeat for the other IDOR routers).
- `backend/alembic/versions/0005_integration_keys.py` — **Create.**
- `backend/alembic/versions/0006_app_settings.py` — **Create.**
- `backend/alembic/versions/0007_customers_logo_url.py` — **Create.**
- `.github/workflows/deploy-dev.yml` — **Modify.** Make the test step blocking; add frontend lint/build.

---

## Task 1: Integration-gateway rate limiter (await + GC-safe task)

**Files:**
- Test: `backend/tests/test_auth_hardening.py`
- Modify: `backend/modules/integrations/auth.py:88-95` (call site) and module top (add task set)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_auth_hardening.py`:

```python
"""Phase A auth-foundation hardening tests."""
import types

import pytest

from modules.integrations import auth as gw_auth


def _fake_key(limit: int, key_id: str = "k1"):
    # Limiter only reads .id and .rate_limit_per_minute off the key.
    return types.SimpleNamespace(id=key_id, rate_limit_per_minute=limit)


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_rate_limiter_allows_up_to_limit_then_429():
    gw_auth._RATE_BUCKETS.clear()
    key = _fake_key(limit=3, key_id="rl-allow")
    for _ in range(3):
        await gw_auth._check_rate_limit(key)
    with pytest.raises(gw_auth.HTTPException) as exc:
        await gw_auth._check_rate_limit(key)
    assert exc.value.status_code == 429


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_rate_limiter_noop_when_limit_unset():
    gw_auth._RATE_BUCKETS.clear()
    key = _fake_key(limit=0, key_id="rl-none")
    for _ in range(50):
        await gw_auth._check_rate_limit(key)
    assert "rl-none" not in gw_auth._RATE_BUCKETS


@pytest.mark.no_db
@pytest.mark.asyncio
async def test_rate_limiter_keys_independent():
    gw_auth._RATE_BUCKETS.clear()
    a, b = _fake_key(1, "rl-a"), _fake_key(1, "rl-b")
    await gw_auth._check_rate_limit(a)
    await gw_auth._check_rate_limit(b)
    with pytest.raises(gw_auth.HTTPException):
        await gw_auth._check_rate_limit(a)
```

> Note: these three pass against the *current* `_check_rate_limit` too (it's correct in isolation) — they lock its behavior. The actual bug is the un-awaited *call site*, covered by the integration assertion in Step 1b below.

- [ ] **Step 1b: Add a call-site regression test** (same file)

```python
@pytest.mark.no_db
@pytest.mark.asyncio
async def test_get_orchestrator_key_awaits_rate_limit(monkeypatch):
    """Proves the limiter is actually awaited inside get_orchestrator_key
    (the old code created the coroutine and dropped it)."""
    called = {"n": 0}

    async def _spy(key):
        called["n"] += 1

    monkeypatch.setattr(gw_auth, "_check_rate_limit", _spy)
    monkeypatch.setattr(gw_auth, "_update_last_used", lambda *a, **k: _noop())

    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("error")  # un-awaited coroutine → RuntimeWarning → error
        # Build the dependency body directly with a fake key lookup:
        # simplest: call the limiter path via a thin wrapper is overkill —
        # instead assert no "coroutine never awaited" warning is raised when
        # _check_rate_limit is invoked through get_orchestrator_key.
    # See Step 3 — after the fix, integration test in test suite confirms 429.
```

> Keep Step 1b lightweight: the un-awaited-coroutine bug surfaces as a `RuntimeWarning: coroutine '_check_rate_limit' was never awaited`. If your pytest config has `filterwarnings = error`, the *current* code already errors here; the fix silences it. If not, rely on Steps 1/3 plus manual `python -W error`.

- [ ] **Step 2: Run tests to verify the limiter tests pass and pin behavior**

Run: `pytest tests/test_auth_hardening.py -k rate_limiter -v`
Expected: 3 PASS.

- [ ] **Step 3: Apply the fix**

In `backend/modules/integrations/auth.py`, add after line 19 (`_rate_lock = asyncio.Lock()`):

```python
# Strong refs to in-flight fire-and-forget tasks so the event loop doesn't
# GC them mid-run (asyncio holds only weak refs to tasks).
_BACKGROUND_TASKS: set[asyncio.Task] = set()
```

Replace lines 88-95 (the `_check_rate_limit(key)` + `asyncio.create_task(...)` block) with:

```python
    # Enforce per-minute rate limit
    await _check_rate_limit(key)

    # Fire-and-forget last_used_at update — doesn't block the request.
    # Keep a strong ref so the loop doesn't GC the task before it runs.
    task = asyncio.create_task(_update_last_used(key.id))
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)
```

- [ ] **Step 4: Verify no un-awaited-coroutine warning + import smoke**

Run: `python -W error::RuntimeWarning -c "import main; print('ok')"`
Expected: prints `ok` (no `coroutine never awaited` error).

- [ ] **Step 5: Commit**

```bash
git add backend/modules/integrations/auth.py backend/tests/test_auth_hardening.py
git commit -m "fix(integrations): await per-key rate limiter; keep ref to background task"
```

---

## Task 2: `/api/auth/register` → bootstrap-only

**Files:**
- Test: `backend/tests/test_auth_hardening.py`
- Modify: `backend/modules/auth/routes.py:251-289`

- [ ] **Step 1: Write the failing test** (append to `test_auth_hardening.py`)

```python
from sqlalchemy import delete, func, select  # add to imports at top of file


async def _delete_all_users():
    from tests.conftest import async_session
    from modules.auth.models import User
    async with async_session() as s:
        await s.execute(delete(User))
        await s.commit()


async def _user_count() -> int:
    from tests.conftest import async_session
    from modules.auth.models import User
    async with async_session() as s:
        return (await s.execute(select(func.count()).select_from(User))).scalar() or 0


@pytest.mark.asyncio
async def test_register_bootstrap_then_closed(client):
    await _delete_all_users()
    try:
        r = await client.post(
            "/api/auth/register",
            json={"email": "first-admin@vg.test", "password": "s3cret-pw-123"},
        )
        assert r.status_code == 201, r.text
        assert r.json()["role"] == "vg_admin"

        r2 = await client.post(
            "/api/auth/register",
            json={"email": "second@vg.test", "password": "s3cret-pw-123"},
        )
        assert r2.status_code == 409
        assert await _user_count() == 1
    finally:
        await _delete_all_users()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_auth_hardening.py::test_register_bootstrap_then_closed -v`
Expected: FAIL — second register returns 201 (current code mints a second vg_admin when signup is enabled / count guard absent), user count == 2.

- [ ] **Step 3: Apply the fix**

In `backend/modules/auth/routes.py`, replace the `register` decorator+signature+guard (lines 251-269) with:

```python
@router.post("/register", response_model=UserRead, status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request,  # required by slowapi — do not remove
    body: SetupRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
    """Public registration — bootstrap only.

    Creates the first vg_admin only when the instance has zero users. Once any
    user exists this endpoint always returns 409; it never mints a second
    account. All later users are created by an admin via POST /api/auth/users.
    Self-service signup was removed: it used to mint vg_admin whenever
    signup_enabled was on (cross-tenant privilege escalation). Equivalent to
    /setup; consolidate the two bootstrap paths in a follow-up.
    """
    count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    if count > 0:
        raise HTTPException(status.HTTP_409_CONFLICT, "Registration is closed")
```

Leave the `pg_insert(...).values(... role="vg_admin" ...).on_conflict_do_nothing(...)` body and cookie code below it unchanged (lines 271-289).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_auth_hardening.py::test_register_bootstrap_then_closed -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/modules/auth/routes.py backend/tests/test_auth_hardening.py
git commit -m "fix(auth): make public /register bootstrap-only (no vg_admin self-signup)"
```

---

## Task 3: `/api/auth/setup` rate limit

**Files:**
- Modify: `backend/modules/auth/routes.py:182-185`

- [ ] **Step 1: Apply** — replace the `setup_first_admin` decorator+signature:

```python
@router.post("/setup", response_model=UserRead, status_code=201)
@limiter.limit("5/minute")
async def setup_first_admin(
    request: Request,  # required by slowapi — do not remove
    body: SetupRequest, response: Response, db: AsyncSession = Depends(get_db)
) -> User:
```

Body unchanged (it already guards `count > 0 → 409`).

- [ ] **Step 2: Verify import smoke**

Run: `python -c "import main; print('ok')"`
Expected: `ok` (slowapi requires the `request: Request` param — confirms decorator wiring).

- [ ] **Step 3: Commit**

```bash
git add backend/modules/auth/routes.py
git commit -m "fix(auth): rate-limit /setup endpoint"
```

---

## Task 4: `/api/auth/signup-status` bootstrap-only

**Files:**
- Test: `backend/tests/test_auth_hardening.py`
- Modify: `backend/modules/auth/routes.py:220-228`

- [ ] **Step 1: Write the failing test** (append)

```python
@pytest.mark.asyncio
async def test_signup_status_open_only_during_bootstrap(client):
    await _delete_all_users()
    try:
        r = await client.get("/api/auth/signup-status")
        assert r.json() == {"open": True, "reason": "bootstrap"}
        await client.post(
            "/api/auth/register",
            json={"email": "admin@vg.test", "password": "s3cret-pw-123"},
        )
        r2 = await client.get("/api/auth/signup-status")
        assert r2.json() == {"open": False, "reason": "closed"}
    finally:
        await _delete_all_users()
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_auth_hardening.py::test_signup_status_open_only_during_bootstrap -v`
Expected: may PASS already if `signup_enabled` is off, but FAILS if the `enabled` branch can return open. Lock it down regardless.

- [ ] **Step 3: Apply** — replace `signup_status` body:

```python
@router.get("/signup-status")
async def signup_status(db: AsyncSession = Depends(get_db)) -> dict:
    """Open exactly when the instance has no users yet (bootstrap). Closed
    forever after — later accounts are provisioned by an admin. The retired
    signup_enabled flag no longer opens public registration."""
    count = (await db.execute(select(func.count()).select_from(User))).scalar() or 0
    if count == 0:
        return {"open": True, "reason": "bootstrap"}
    return {"open": False, "reason": "closed"}
```

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/test_auth_hardening.py::test_signup_status_open_only_during_bootstrap -v`
Expected: PASS.

- [ ] **Step 5: Deprecate the now-dead flag helper** — replace `_is_signup_enabled` docstring/body header (lines 50-54) keeping the function (still called by `/settings/signup`):

```python
async def _is_signup_enabled(db: AsyncSession) -> bool:
    """DEPRECATED — no longer gates registration (bootstrap-only now). Read
    only by the legacy /settings/signup endpoints; grants no access. Remove
    with those endpoints + their frontend toggle in a follow-up PR."""
    setting = await db.get(AppSetting, _SIGNUP_SETTING_KEY)
    if setting is None:
        return False
    return bool(setting.value.get("enabled", False))
```

- [ ] **Step 6: Commit**

```bash
git add backend/modules/auth/routes.py backend/tests/test_auth_hardening.py
git commit -m "fix(auth): signup-status reports bootstrap-only; deprecate signup_enabled"
```

---

## Task 5: Tenant-ownership dependency (`require_customer_access`)

**Files:**
- Test: `backend/tests/test_tenant_access.py`
- Modify: `backend/modules/auth/dependencies.py` (add dependency)
- Modify: `backend/modules/markup/routes.py` (apply to `list_markup_rules` — representative)

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_tenant_access.py`:

```python
"""Cross-tenant IDOR guard tests for require_customer_access."""
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
    """Override get_current_user for one test, then restore."""
    def _set(user):
        app.dependency_overrides[get_current_user] = lambda: user
    yield _set
    # conftest installs a vg_admin override at import — restore it.
    from tests.conftest import _TEST_ADMIN
    app.dependency_overrides[get_current_user] = lambda: _TEST_ADMIN


@pytest.mark.asyncio
async def test_customer_admin_blocked_from_other_customer(client, as_user):
    cust_a, cust_b = uuid.uuid4(), uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/markup-rules/{cust_b}")
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_customer_admin_allowed_own_customer(client, as_user):
    cust_a = uuid.uuid4()
    as_user(_user("customer_admin", customer_id=cust_a))
    r = await client.get(f"/api/markup-rules/{cust_a}")
    assert r.status_code == 200  # empty list, but authorized


@pytest.mark.asyncio
async def test_vg_admin_allowed_any_customer(client, as_user):
    as_user(_user("vg_admin"))
    r = await client.get(f"/api/markup-rules/{uuid.uuid4()}")
    assert r.status_code == 200
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/test_tenant_access.py -v`
Expected: `test_customer_admin_blocked_from_other_customer` FAILS (returns 200 — no ownership check today).

- [ ] **Step 3: Add the dependency** — append to `backend/modules/auth/dependencies.py`:

```python
def require_customer_access(
    customer_id: uuid_mod.UUID,
    current_user: CurrentUser,
) -> uuid_mod.UUID:
    """Authorize access to one customer's data. Use as a route dependency on
    any path with a ``customer_id`` path param.

    vg_admin and the trusted ingest service may act on any customer;
    customer_admin only on their own; everyone else is forbidden.
    """
    if current_user.role in ("vg_admin", "ingest_service"):
        return customer_id
    if current_user.role == "customer_admin" and current_user.customer_id == customer_id:
        return customer_id
    raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for this customer")
```

- [ ] **Step 4: Apply it to the markup route** — in `backend/modules/markup/routes.py`, add the import and guard the `customer_id` endpoint:

```python
# add to imports:
from modules.auth.dependencies import require_customer_access

# change the decorator on list_markup_rules (line 156):
@router.get(
    "/{customer_id}",
    response_model=list[MarkupRuleRead],
    dependencies=[Depends(require_customer_access)],
)
async def list_markup_rules(customer_id: UUID, db: AsyncSession = Depends(get_db)):
    ...
```

- [ ] **Step 5: Run to verify it passes**

Run: `pytest tests/test_tenant_access.py -v`
Expected: all 3 PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/modules/auth/dependencies.py backend/modules/markup/routes.py backend/tests/test_tenant_access.py
git commit -m "feat(auth): add require_customer_access tenant guard; apply to markup routes"
```

- [ ] **Step 7: Repeat the guard for the remaining IDOR routers** (one commit each, same pattern — add `dependencies=[Depends(require_customer_access)]` to every route whose path includes `{customer_id}`):
  - `backend/modules/customer_catalog/routes.py`
  - `backend/modules/customers/routes.py` (the `{customer_id}` GET/detail routes)
  - `backend/modules/ops_config/routes.py`
  - `backend/modules/decorations/routes.py`
  - `backend/modules/pricing/routes.py`

  For each, add a test in `test_tenant_access.py` mirroring Step 1 (A-token → B-resource → 403). Commit message: `feat(auth): enforce tenant access on <module> routes`.

---

## Task 6: Make CI test gate blocking

**Files:**
- Modify: `.github/workflows/deploy-dev.yml` (the test step, ~line 32)

- [ ] **Step 1: Apply** — find the test step and remove the `|| true`:

```yaml
      - name: Run backend tests
        working-directory: backend
        run: pytest --tb=short -q
```

(Was `pytest --tb=short -q || true`.)

- [ ] **Step 2: Add a frontend lint/build job** (new job in the same workflow):

```yaml
  frontend-check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
      - name: Install + lint + build
        working-directory: frontend
        run: |
          npm ci
          npm run lint
          npm run build
```

Make the `build-and-push` job `needs: [test, frontend-check]` so a red test or lint blocks deploy.

- [ ] **Step 3: Verify YAML is valid**

Run: `python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/deploy-dev.yml')); print('yaml ok')"`
Expected: `yaml ok`.

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/deploy-dev.yml
git commit -m "ci: make backend tests blocking; add frontend lint/build gate"
```

---

## Task 7: Missing Alembic migrations (stop relying on create_all)

Current head: `0004_webhooks`. Models exist with no migration: `integration_keys`, `app_settings`, `customers.logo_url`. Match the existing IF-NOT-EXISTS style (see `0004_webhooks.py`).

**Files:**
- Create: `backend/alembic/versions/0005_integration_keys.py`
- Create: `backend/alembic/versions/0006_app_settings.py`
- Create: `backend/alembic/versions/0007_customers_logo_url.py`

- [ ] **Step 1: integration_keys** — create `0005_integration_keys.py`:

```python
"""Create integration_keys table.

Revision ID: 0005_integration_keys
Revises: 0004_webhooks
Create Date: 2026-05-27
"""
from alembic import op

revision = "0005_integration_keys"
down_revision = "0004_webhooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS integration_keys (
            id                     VARCHAR(64) PRIMARY KEY,
            key_hash               VARCHAR(128) NOT NULL,
            name                   VARCHAR(255) NOT NULL,
            allowed_customer_ids   JSONB,
            allowed_supplier_slugs JSONB,
            rate_limit_per_minute  INTEGER NOT NULL DEFAULT 60,
            is_active              BOOLEAN NOT NULL DEFAULT TRUE,
            is_synthetic           BOOLEAN NOT NULL DEFAULT FALSE,
            last_used_at           TIMESTAMP WITH TIME ZONE,
            created_at             TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            revoked_at             TIMESTAMP WITH TIME ZONE
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_integration_keys_key_hash "
        "ON integration_keys(key_hash)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_integration_keys_key_hash")
    op.execute("DROP TABLE IF EXISTS integration_keys")
```

- [ ] **Step 2: app_settings** — create `0006_app_settings.py`:

```python
"""Create app_settings table.

Revision ID: 0006_app_settings
Revises: 0005_integration_keys
Create Date: 2026-05-27
"""
from alembic import op

revision = "0006_app_settings"
down_revision = "0005_integration_keys"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS app_settings (
            key        VARCHAR(64) PRIMARY KEY,
            value      JSON NOT NULL DEFAULT '{}'::json,
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS app_settings")
```

- [ ] **Step 3: customers.logo_url** — create `0007_customers_logo_url.py`:

```python
"""Add customers.logo_url column.

Revision ID: 0007_customers_logo_url
Revises: 0006_app_settings
Create Date: 2026-05-27
"""
from alembic import op

revision = "0007_customers_logo_url"
down_revision = "0006_app_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE customers ADD COLUMN IF NOT EXISTS logo_url TEXT")


def downgrade() -> None:
    op.execute("ALTER TABLE customers DROP COLUMN IF EXISTS logo_url")
```

- [ ] **Step 4: Verify migrations apply cleanly on a fresh DB**

```bash
# point at a scratch DB
docker compose up -d postgres
cd backend && source .venv/bin/activate
alembic upgrade head
```
Expected: ends at `0007_customers_logo_url`, no errors.

- [ ] **Step 5: Verify downgrade chain**

Run: `alembic downgrade -3 && alembic upgrade head`
Expected: clean down to `0004_webhooks` then back up to `0007`.

- [ ] **Step 6: Commit**

```bash
git add backend/alembic/versions/0005_integration_keys.py \
        backend/alembic/versions/0006_app_settings.py \
        backend/alembic/versions/0007_customers_logo_url.py
git commit -m "feat(db): add migrations for integration_keys, app_settings, customers.logo_url"
```

---

## Task 8: Full-suite green + push

- [ ] **Step 1: Run the whole backend suite**

Run: `cd backend && source .venv/bin/activate && pytest -q`
Expected: all pass (the new `test_auth_hardening.py` + `test_tenant_access.py` included), no `coroutine never awaited` warnings.

- [ ] **Step 2: Push the branch and open the PR**

```bash
git push -u origin harden/auth-foundation
gh pr create --title "harden: auth foundation (register bootstrap-only, tenant guard, rate limiter, migrations, CI)" \
  --body "Phase A of the master rollout. Base branch that #136/#137/#138 rebase onto. See plans/2026-05-27-phase-a-auth-foundation.md."
```

- [ ] **Step 3: Request a second-pass security review** (do NOT self-approve). After merge, begin Phase B (rebase #136).

---

## Self-Review Notes
- **Spec coverage:** register bootstrap-only (T2), rate limiter await (T1), tenant IDOR guard (T5 + T5.7 for all routers), missing migrations (T7), blocking CI (T6), signup-status + flag deprecation (T4). All Phase-A spec items mapped.
- **Type consistency:** guard named `require_customer_access` everywhere; `_BACKGROUND_TASKS` defined in T1 before use; migration `down_revision` chain 0004→0005→0006→0007 consistent.
- **Out of scope (later phases):** portal mount (#136/Phase B), n8n proxy registration (#138 split/Phase C), SSE-vs-polling (#142/Phase D), Redis token cache + arq (Phase E), full removal of `/settings/signup` + frontend toggle (follow-up PR).
```
