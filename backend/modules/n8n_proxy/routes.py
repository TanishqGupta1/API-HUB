"""Proxy endpoints for n8n — lets the Next.js frontend browse + trigger
workflows without exposing the n8n API key to the browser.

All routes authenticate upstream via `N8N_API_KEY` and return condensed
JSON shapes suitable for UI consumption.
"""
import os
from contextlib import asynccontextmanager
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/api/n8n", tags=["n8n-proxy"])

# Module-level client — reused across requests (connection pooling)
_http_client: httpx.AsyncClient | None = None


def _key() -> str:
    value = os.getenv("N8N_API_KEY")
    if not value:
        raise HTTPException(500, "N8N_API_KEY not configured")
    return value


def _base() -> str:
    return os.getenv("N8N_BASE_URL", "http://localhost:5678").rstrip("/")


def _webhook_base() -> str:
    return os.getenv("N8N_WEBHOOK_BASE", _base()).rstrip("/")


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
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        # Fallback for dashboard stability during n8n boot-up
        print(f"n8n proxy warning: {str(e)}")
        return []

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
    except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
        print(f"n8n proxy warning (executions): {str(e)}")
        return []

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


@router.post("/workflows/{workflow_id}/trigger")
async def trigger_workflow(workflow_id: str, request: Request):
    """Trigger workflow via its first webhook path, forwarding query params as POST body."""
    params = dict(request.query_params)
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
    async with httpx.AsyncClient(timeout=10.0) as c:
        r = await c.post(trigger_url, json=params)
        r.raise_for_status()
        return {"triggered": True, "url": trigger_url, "response": r.json()}
