# n8n Integration Contract

API-HUB treats n8n as an external workflow engine. This document is the
formal interface between the FastAPI backend and any n8n instance.

---

## 1. Environment requirements

n8n must be a host that supports community nodes:
- Self-hosted Docker (recommended — use `n8n.Dockerfile` from this repo)
- ECS Fargate (Phase 14d)
- n8n.cloud Pro+ (manual community-node install)
- Render, Fly, Railway, etc.

**Not supported:** n8n.cloud Starter — community nodes are blocked on that
tier and the OnPrintShop node will not load.

---

## 2. Required env vars

### On the FastAPI backend

| Var | Purpose | Required in prod |
|-----|---------|-----------------|
| `N8N_API_BASE_URL` | Base URL of the n8n REST API | Yes |
| `N8N_API_KEY` | n8n REST API key (Settings → API) | Yes |
| `N8N_WEBHOOK_BASE_URL` | Base URL for n8n webhook triggers | Yes |
| `N8N_PUSH_WEBHOOK_URL` | Full URL of the OPS push webhook | Yes |

### On the n8n container

| Var | Purpose |
|-----|---------|
| `API_BASE_URL` | Base URL of the FastAPI backend |
| `INGEST_SHARED_SECRET` | Value for `X-Ingest-Secret` header on inbound calls |

---

## 3. Outbound: backend → n8n webhooks

**Trigger:** FastAPI POSTs to `N8N_PUSH_WEBHOOK_URL`.

**Headers:**
- `Content-Type: application/json`

**OPS push payload** (defined in `backend/modules/ops_push/service.py`):

```json
{
  "push_log_id": "uuid",
  "customer_id": "uuid",
  "product_id": "uuid",
  "payload": {
    "external_id": "supplier-sku",
    "name": "Product Name",
    "variants": [],
    "options": []
  },
  "ops_auth": {
    "base_url": "https://customer-ops.example.com",
    "token_url": "https://customer-ops.example.com/oauth/token",
    "client_id": "...",
    "client_secret": "..."
  }
}
```

**Response:**
- `2xx` — workflow accepted; backend leaves `push_log.status = "pending"`
- `4xx`/`5xx` — `httpx` raises; backend flips `push_log.status = "failed"`

**Security:** `ops_auth.client_secret` is in the request body. The webhook
URL must point inside a private network. Public-internet n8n hosts must
terminate TLS before this URL.

---

## 4. Inbound: n8n → backend ingest

**Endpoints:** `POST /api/ingest/{supplier_id}/products`, `categories`,
`inventory`, `pricing`, `master-options`.

**Headers:**
- `Content-Type: application/json`
- `X-Ingest-Secret: <INGEST_SHARED_SECRET>` (401 if missing or wrong)

**Body shapes:** see `backend/modules/catalog/ingest.py` (Pydantic models).

---

## 5. Inbound: n8n → backend push callback

After n8n calls OPS GraphQL and receives the real `ops_product_id`, it
must call back to flip the push log:

```
POST /api/push/{push_log_id}/callback
Headers:
  X-Ingest-Secret: <INGEST_SHARED_SECRET>
Body:
  {
    "status": "success" | "failed",
    "ops_product_id": "12345" | null,
    "error": null | "OPS error message"
  }
```

> Endpoint to be added in a follow-up — see issue #83.

---

## 6. Self-host setup checklist

1. Build the custom image: `docker build -f n8n.Dockerfile -t api-hub-n8n:latest .`
2. Run it; open the n8n editor and create the admin account.
3. Settings → API → generate an API key. Copy it.
4. Set env vars on the n8n container: `API_BASE_URL`, `INGEST_SHARED_SECRET`.
5. Set env vars on the FastAPI backend: `N8N_API_BASE_URL`, `N8N_API_KEY`,
   `N8N_WEBHOOK_BASE_URL`, `N8N_PUSH_WEBHOOK_URL`.
6. Import workflow JSONs from `n8n-workflows/` via Workflow → Import from File.
7. Open each imported workflow once and click Save so the workflow_id is stable.
8. Activate the workflows you need (cron syncs, OPS push).
9. Smoke test: `curl -s http://api:8000/health` then trigger a sync manually.

---

## 7. Existing-install migration

1. Source n8n: Workflows → Export All → save the bundle.
2. Source n8n: `n8n export:credentials --backup --output=creds.json`
   (credentials are AES-256 encrypted with `N8N_ENCRYPTION_KEY` — preserve
   this env var across hosts or re-create credentials manually).
3. Destination n8n: Workflows → Import bundle.
4. Destination n8n: `n8n import:credentials --input=creds.json`
5. Re-activate workflows.
