# Task — Phase 8 T9: n8n Push Path Retirement

**Owner:** Vidhi
**Date:** 2026-05-15
**Status:** ✅ Done
**Commit:** `29b7308`
**Related plan:** `docs/superpowers/plans/2026-05-08-sanmar-ops-staging-push.md`
**Related doc:** `docs/May/1_may/13_may/phase8_task9_done.md`

---

## What is this?

Before Phase 8, the only way to push a product from API-HUB to OnPrintShop (OPS) was through n8n. A request would arrive at FastAPI, FastAPI would POST a payload to an n8n webhook URL, and then n8n would run the push workflow — calling OPS GraphQL mutations through the `n8n-nodes-onprintshop` custom node.

FastAPI was essentially a middleman that called n8n, and n8n was the real actor. FastAPI had no idea what happened after the webhook fired.

**Phase 8 changed this.** The Integration Gateway (Tasks 8 and 9) moves the entire push logic into FastAPI. n8n is no longer in the push path at all. 

Task 9 is the cleanup side of this migration: it removes all the old n8n code that used to trigger the push, marks the old route as deprecated, and archives the n8n workflow JSON so it's preserved but not accidentally used.

---

## Why was this task necessary?

### The old code was still there even after the gateway was live

When Task 8 (gateway core) was completed on 2026-05-13, the new `prepare_push_intent()` and `execute_push()` functions were working. But the old code was never deleted:

- `trigger_n8n_push()` in `service.py` was still sitting there, even though the admin push route was no longer calling it
- The `n8n_proxy` router was still registered in `main.py`, exposing workflow management endpoints that are no longer part of the push pipeline
- `N8N_WEBHOOK_BASE_URL` was still listed as a required environment variable in production, meaning any deployment without this env var would refuse to start
- The ops-push.json n8n workflow was still in the main workflows folder, looking like an active workflow

This created a confusing state: the code was doing the right thing in production (using the gateway), but the old code was still present and could be mistakenly called or relied on.

### The spec is explicit: no n8n in the push path for beta

The Phase 8 spec constraint (see `docs/superpowers/specs/2026-05-11-integration-gateway-design.md`) states:

> *No n8n in OPS push path for beta. Push runs in FastAPI process.*

Having dead n8n push code sitting around violates the spirit of that constraint even if it's not being called. A future developer might see `trigger_n8n_push()` and think it's the right function to use.

### Keeping unused env vars in the required list breaks deployments

`N8N_WEBHOOK_BASE_URL` was listed in `_PROD_REQUIRED_ENV_VARS` in `main.py`. This means if this env var is not set, the app refuses to start in production with:
```
RuntimeError: Production startup blocked. Missing required env vars: N8N_WEBHOOK_BASE_URL
```

If a new developer sets up a production deployment and doesn't know about this legacy requirement, they're locked out. An env var that isn't actually used by any running code should not be required.

---

## How does it connect to the existing codebase?

This task touched four places in the codebase:

### 1. `backend/modules/ops_push/service.py` — the push entry point

This is the file the admin UI push button calls. It has a function called `push_product()` which the admin route (`POST /api/push/{customer_id}/{product_id}`) calls when an operator clicks "Push to OPS" in the admin panel.

Before Phase 8, `push_product()` worked like this:
```
operator clicks push button
  → push_product() builds a payload
  → trigger_n8n_push() fires a POST to N8N_PUSH_WEBHOOK_URL
  → n8n receives the payload and runs the push workflow
  → FastAPI returns "ok" without knowing the outcome
```

After Phase 8, `push_product()` was already calling `prepare_push_intent()` and `execute_push()` from the gateway. The `trigger_n8n_push()` function was still in the file but never called.

**What was removed:** The entire `trigger_n8n_push()` function (15 lines) and the now-unused imports: `os`, `httpx`, `Any`.

### 2. `backend/main.py` — the app entrypoint

`main.py` is where FastAPI starts and all routes are registered. It had three n8n-related things that needed removing:

**Import:** `from modules.n8n_proxy.routes import router as n8n_proxy_router`

The n8n_proxy module provided UI endpoints for browsing n8n workflows (`GET /api/n8n/workflows`), viewing executions, and triggering workflows. These were useful when n8n was the push engine. Now that FastAPI owns the push, these browsing endpoints are not needed as part of the core push infrastructure.

**Router registration:** `app.include_router(n8n_proxy_router, dependencies=_auth)`

This line exposed all the `n8n_proxy` routes. Removing it means `GET /api/n8n/workflows` and similar routes return 404 instead of proxying to n8n.

**Lifespan cleanup:** 
```python
from modules.n8n_proxy import routes as _n8n_proxy
if _n8n_proxy._http_client is not None:
    await _n8n_proxy._http_client.aclose()
```
The n8n proxy module kept a reusable `httpx.AsyncClient` in memory to avoid recreating connections on every request. This cleanup code in the app shutdown handler properly closed that client. Removing the module means removing the cleanup too.

**Required env var:** `N8N_WEBHOOK_BASE_URL` was removed from the production env var checklist.

### 3. `backend/modules/ops_push/routes.py` — the old push route

The route `POST /api/push/{customer_id}/{product_id}` is the original admin push endpoint. It still works — it calls `push_product()` in `service.py` which calls the gateway. But it's the "old" way to push. The "new" way is through the integration gateway at `POST /api/integrations/v1/push-requests`.

Adding `deprecated=True` to the route decorator:
```python
@router.post("/{customer_id}/{product_id}", deprecated=True)
```
...tells FastAPI to mark this route as deprecated in the OpenAPI docs (Swagger UI). It still works perfectly — the operator push button in the admin UI still calls it — but it's flagged so developers know to migrate away from it.

### 4. `n8n-workflows/ops-push.json` — the n8n workflow definition

This is the JSON export of the n8n workflow that used to handle OPS push. It defined the workflow nodes, their connections, and configuration. Moving it to `deprecated/` preserves the history (useful if someone needs to understand what the old push did) but removes it from the active workflows folder so n8n doesn't pick it up and run it.

The tombstone README explains:
- Why it was deprecated
- What replaced it
- When it was retired

---

## What was done step by step

### Step 1: Removed `trigger_n8n_push()` from `service.py`

The function looked like this:
```python
async def trigger_n8n_push(payload: dict[str, Any]) -> None:
    webhook_url = os.getenv("N8N_PUSH_WEBHOOK_URL", "").strip()
    if not webhook_url:
        if os.getenv("ENVIRONMENT", "development").lower() == "production":
            raise RuntimeError("N8N_PUSH_WEBHOOK_URL is required in production")
        return
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(webhook_url, json=payload)
        response.raise_for_status()
```

Deleted the entire function. Also cleaned up the now-unused imports at the top of the file: `os`, `httpx`, `Any` (the type hint). `CustomerProductSelection` was moved to be imported alongside the other catalog models at the import it was already using — a minor cleanup that came with the import rewrite.

### Step 2: Removed n8n proxy from `main.py`

Three deletions:
1. The import line
2. The `app.include_router(n8n_proxy_router, ...)` line
3. The 3-line lifespan shutdown handler for the proxy's HTTP client

Also removed `N8N_WEBHOOK_BASE_URL` from the `_PROD_REQUIRED_ENV_VARS` tuple.

### Step 3: Marked old push route deprecated

One-word change in `routes.py`:
```python
# Before:
@router.post("/{customer_id}/{product_id}")

# After:
@router.post("/{customer_id}/{product_id}", deprecated=True)
```

The route still functions. The admin UI still uses it. But in the Swagger UI (`/docs`) it now appears with a strikethrough, signaling to any developer integrating with the API that they should use `/api/integrations/v1/push-requests` instead.

### Step 4: Archived the n8n workflow

Created `n8n-workflows/deprecated/` directory and moved `ops-push.json` into it. Created `deprecated/README.md` that explains:
- The file is kept for reference only
- It was superseded by the Integration Gateway on 2026-05-15
- The replacement is `POST /api/integrations/v1/push-requests`

---

## Tests that had to be updated

Removing n8n code broke two tests that were testing the old n8n integration:

**`test_admin_route_no_n8n_webhook_trigger`** in `test_admin_route_preserved.py`:
This test was checking that the admin push route doesn't call `trigger_n8n_push()`. It used `monkeypatch.setattr("modules.ops_push.service.trigger_n8n_push", _spy)`. Once `trigger_n8n_push` was deleted from `service.py`, `monkeypatch.setattr` raised `AttributeError` because the attribute no longer exists. The test was deleted — there's nothing to spy on anymore because the n8n code is gone.

**`test_production_mode_fails_when_n8n_webhook_base_url_missing`** in `test_n8n_url_config.py`:
This test verified that production startup fails when `N8N_WEBHOOK_BASE_URL` is not set. After removing `N8N_WEBHOOK_BASE_URL` from the required env vars list, this assertion was wrong. The test was removed.

---

## How can this be modified in the future?

### If the n8n proxy endpoints are still needed by the frontend

The Workflows page in the admin UI may call `GET /api/n8n/workflows` to list n8n workflows. If the frontend still needs those endpoints, the n8n_proxy module can be re-registered in `main.py` — it's not deleted, just unregistered. The Workflows page functionality is separate from the push pipeline and can coexist.

### Re-enabling the deprecated route

If the admin UI gets updated to call the new integration gateway directly (`/api/integrations/v1/push-requests`), the old route can be deleted entirely from `routes.py`. Until then, `deprecated=True` is the right signal — "it works, but use the new one."

### If n8n comes back as an orchestrator

n8n can still push products by calling `POST /api/integrations/v1/push-requests` with an `X-Orchestrator-Key`. It becomes one consumer of the gateway, not the gatekeeper. An n8n workflow could make an HTTP Request node call to the gateway endpoint. The archived `ops-push.json` can be used as a reference for what that workflow should look like, adapted to call the gateway instead of OPS directly.

### Future cleanup: delete n8n_proxy entirely

If the Workflows page in the admin UI gets redesigned and no longer needs to list n8n workflows, the `backend/modules/n8n_proxy/` directory can be deleted completely. Its routes are already disconnected — it's just taking up space at that point.
