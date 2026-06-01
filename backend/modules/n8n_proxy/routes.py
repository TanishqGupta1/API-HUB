"""Proxy endpoints for n8n — lets the Next.js frontend browse + trigger
workflows without exposing the n8n API key to the browser.

All routes authenticate upstream via `N8N_API_KEY` and return condensed
JSON shapes suitable for UI consumption.
"""
import logging
import os
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from modules.auth.dependencies import _require_vg_admin

log = logging.getLogger(__name__)

# vg_admin only. The role check runs before any handler body (so an
# unauthorized caller gets 403 before we ever touch N8N_API_KEY), and
# /api/n8n is intentionally absent from the ingest path allow-list, so
# service tokens cannot reach these routes either.
router = APIRouter(
    prefix="/api/n8n",
    tags=["n8n-proxy"],
    dependencies=[Depends(_require_vg_admin)],
)

# Module-level client — reused across requests (connection pooling)
_http_client: httpx.AsyncClient | None = None


def _key() -> str:
    value = os.getenv("N8N_API_KEY")
    if not value:
        # Don't echo the env var name to the client — log it, return a generic
        # 503 to the caller.
        log.error("n8n proxy misconfigured: N8N_API_KEY is not set")
        raise HTTPException(503, "n8n service is currently unavailable")
    return value


def _base() -> str:
    # N8N_API_BASE_URL is the canonical var; N8N_BASE_URL kept for backward compat
    url = os.getenv("N8N_API_BASE_URL") or os.getenv("N8N_BASE_URL")
    if url:
        return url.rstrip("/")
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        raise RuntimeError(
            "N8N_API_BASE_URL must be set in production. "
            "In ECS this comes from the task definition; in dev set it in .env."
        )
    return "http://n8n:5678"


def _webhook_base() -> str:
    return (os.getenv("N8N_WEBHOOK_BASE_URL") or os.getenv("N8N_WEBHOOK_BASE") or _base()).rstrip("/")


def _client() -> httpx.AsyncClient:
    """Return the module-level client, creating it lazily if needed."""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=_base(),
            headers={"X-N8N-API-KEY": _key()},
            timeout=15.0,
        )
    return _http_client


@router.get("/workflows")
async def list_workflows():
    c = _client()
    try:
        r = await c.get("/api/v1/workflows", params={"limit": 50})
        r.raise_for_status()
        body = r.json()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        log.warning("n8n unreachable when listing workflows: %s", e)
        raise HTTPException(503, "n8n service is currently unreachable")
    except httpx.HTTPStatusError as e:
        log.error(
            "n8n returned %s when listing workflows: %s",
            e.response.status_code,
            e.response.text[:300],
        )
        raise HTTPException(502, f"n8n upstream error ({e.response.status_code})")

    out = []
    for w in body.get("data", []):
        nodes = w.get("nodes", [])
        webhook_nodes = [n for n in nodes if n.get("type") == "n8n-nodes-base.webhook"]
        webhook_paths = [
            n.get("parameters", {}).get("path") for n in webhook_nodes
        ]
        webhook_paths = [p for p in webhook_paths if p]
        trigger_names = [
            n.get("name") for n in nodes
            if "trigger" in n.get("type", "").lower()
               or n.get("type") == "n8n-nodes-base.webhook"
        ]
        out.append({
            "id": w["id"],
            "name": w.get("name"),
            "active": w.get("active", False),
            "updatedAt": w.get("updatedAt"),
            "triggers": trigger_names,
            "webhook_url": f"{_webhook_base()}/webhook/{webhook_paths[0]}" if webhook_paths else None,
            "node_count": len(nodes),
        })
    return out


@router.get("/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    c = _client()
    try:
        r = await c.get(f"/api/v1/workflows/{workflow_id}")
        if r.status_code == 404:
            raise HTTPException(404, "Workflow not found")
        r.raise_for_status()
        return r.json()
    except (httpx.ConnectError, httpx.TimeoutException):
        raise HTTPException(503, "n8n service is currently unreachable")


@router.get("/executions")
async def list_executions(workflow_id: Optional[str] = None, limit: int = 20):
    params: dict = {"limit": limit}
    if workflow_id:
        params["workflowId"] = workflow_id
    c = _client()
    try:
        r = await c.get("/api/v1/executions", params=params)
        r.raise_for_status()
        body = r.json()
    except (httpx.ConnectError, httpx.TimeoutException) as e:
        log.warning("n8n unreachable when listing executions: %s", e)
        raise HTTPException(503, "n8n service is currently unreachable")
    except httpx.HTTPStatusError as e:
        log.error(
            "n8n returned %s when listing executions: %s",
            e.response.status_code,
            e.response.text[:300],
        )
        raise HTTPException(502, f"n8n upstream error ({e.response.status_code})")

    return [
        {
            "id": e.get("id"),
            "workflowId": e.get("workflowId"),
            "status": e.get("status"),
            "startedAt": e.get("startedAt"),
            "stoppedAt": e.get("stoppedAt"),
            "finished": e.get("finished"),
            "mode": e.get("mode"),
        }
        for e in body.get("data", [])
    ]


async def trigger_workflow_by_id(workflow_id: str, params: dict | None = None) -> dict:
    """Trigger a workflow via its first webhook path. Internal helper — callable
    from other modules without constructing a Request object."""
    params = params or {}
    c = _client()
    try:
        r = await c.get(f"/api/v1/workflows/{workflow_id}")
        if r.status_code == 404:
            raise HTTPException(404, "Workflow not found")
        r.raise_for_status()
        w = r.json()
    except (httpx.ConnectError, httpx.TimeoutException):
        raise HTTPException(503, "n8n service is currently unreachable")

    if not w.get("active"):
        raise HTTPException(409, f"Workflow '{w.get('name')}' is not active")

    webhook_path = None
    for n in w.get("nodes", []):
        if n.get("type") == "n8n-nodes-base.webhook":
            webhook_path = n.get("parameters", {}).get("path")
            break

    if not webhook_path:
        raise HTTPException(
            409, f"Workflow '{w.get('name')}' has no webhook trigger"
        )

    trigger_url = f"{_base()}/webhook/{webhook_path}"
    async with httpx.AsyncClient(timeout=10.0) as hc:
        try:
            tr = await hc.post(trigger_url, json=params)
            tr.raise_for_status()
        except httpx.HTTPStatusError as e:
            # n8n returned 4xx/5xx — surface a clean HTTPException so FastAPI
            # produces a JSON response that CORSMiddleware can decorate (avoids
            # opaque "blocked by CORS policy" errors in the browser).
            detail = e.response.text or f"n8n webhook returned {e.response.status_code}"
            raise HTTPException(status_code=502, detail=f"n8n webhook error: {detail[:300]}")
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise HTTPException(status_code=503, detail=f"n8n unreachable: {e}")
        try:
            body = tr.json()
        except ValueError:
            body = {"raw": tr.text}
        return {"triggered": True, "url": trigger_url, "response": body}


@router.post("/workflows/{workflow_id}/trigger")
async def trigger_workflow(workflow_id: str, request: Request):
    """Trigger workflow via its first webhook path, forwarding query params as POST body."""
    return await trigger_workflow_by_id(workflow_id, dict(request.query_params))
