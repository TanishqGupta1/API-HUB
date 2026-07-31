# External n8n Setup

Step-by-step procedure for pointing API-HUB at an n8n instance running **outside** the local Docker stack — e.g. n8n.cloud Pro+, Render, Fly, Railway, or a separate EC2 / VPS.

This is the canonical path for staging + production. The bundled `n8n` Compose service (gated behind `--profile dev`) is for quick local testing only.

For the architecture rationale, see `docs/superpowers/specs/2026-05-04-phase14-prod-ready-design.md` decisions D2 (keep n8n) and D4 (custom Docker image).

---

## Prerequisites

- An n8n host that supports **community nodes** (OnPrintShop is one)
  - ✅ n8n.cloud Pro+ ($20/mo and up)
  - ✅ Self-hosted Docker (use this repo's `n8n.Dockerfile`)
  - ✅ Render, Fly, Railway, Hetzner — anywhere Docker runs
  - ❌ n8n.cloud Starter — community nodes blocked

- The n8n host and the API-HUB backend must be able to reach each other over HTTPS:
  - n8n → backend: hits `/api/ingest/...` endpoints
  - backend → n8n: hits `/webhook/...` URLs and the n8n REST API

- `INGEST_SHARED_SECRET` value picked (random 32+ bytes); will go in BOTH backend and n8n env

---

## Phase 1 — Bring up the external n8n

Pick one of three paths.

### 1A — n8n.cloud Pro+

1. Sign up at https://n8n.cloud, pick the Pro plan
2. After provisioning, go to Settings → Community Nodes
3. Add the OnPrintShop node:
   - If published to npm: paste the package name `@visualgraphx/n8n-nodes-onprintshop` and install
   - Or upload the tarball: `cd n8n-nodes-onprintshop && npm pack` to produce `.tgz`, upload via UI
4. Settings → Variables → add `API_BASE_URL` and `INGEST_SHARED_SECRET`
5. Settings → Auth → enable basic auth (or SSO on Enterprise)

### 1B — Self-hosted Docker (Render, Fly, Railway, EC2)

Build the custom image from this repo:

```bash
docker build -f n8n.Dockerfile -t api-hub-n8n:latest .
```

Push to your registry (ECR, Docker Hub, GHCR):

```bash
docker tag api-hub-n8n:latest <registry>/api-hub-n8n:latest
docker push <registry>/api-hub-n8n:latest
```

Deploy on your platform with these container env vars:

```
N8N_HOST=0.0.0.0
N8N_PORT=5678
N8N_PROTOCOL=https
N8N_EDITOR_BASE_URL=https://n8n.yourdomain.com
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=<strong-password>
API_BASE_URL=https://api.yourdomain.com
INGEST_SHARED_SECRET=<same value the backend uses>
```

Mount a persistent volume at `/home/node/.n8n` for workflow + credential data.

### 1C — Existing n8n install

If you already run n8n elsewhere, install the OnPrintShop node manually:

```bash
# Inside the n8n host
mkdir -p ~/.n8n/nodes
cd ~/.n8n/nodes
npm install <repo-checkout>/n8n-nodes-onprintshop
# Or via the bundled tarball produced by `npm pack`
```

Restart n8n. Verify the node loads — check startup logs for `n8n-nodes-onprintshop`.

---

## Phase 2 — Configure the n8n side

After the n8n editor is reachable:

1. Visit n8n editor (e.g. `https://n8n.yourdomain.com`), log in
2. Workflows → Import from File → upload each `.json` in `n8n-workflows/` from this repo
3. For each imported workflow:
   - Open it
   - Click any HTTP Request node, verify it references `{{ $env.API_BASE_URL }}` (not a hardcoded URL)
   - Click any node that uses `INGEST_SHARED_SECRET` and confirm it reads from env
   - Activate the workflow (top-right toggle) if it's cron- or webhook-triggered
4. Settings → Credentials → create OPS OAuth credentials:
   - Type: OAuth2
   - Auth URL, Token URL, Client ID, Client Secret — get from OPS account
   - Test the connection
5. Settings → API → Create API Key. **Save the key** — backend needs it.

---

## Phase 3 — Configure the backend to point at external n8n

### 3A — Local dev (`.env`)

Edit `api-hub/.env`:

```bash
# Backend → external n8n
N8N_API_BASE_URL=https://n8n.yourdomain.com
N8N_WEBHOOK_BASE_URL=https://n8n.yourdomain.com
N8N_PUSH_WEBHOOK_URL=https://n8n.yourdomain.com/webhook/vg-ops-push-001
N8N_API_KEY=<key from Phase 2.5>

# Must match the n8n side
INGEST_SHARED_SECRET=<same value n8n sees>
```

Stop the bundled n8n if it was running:

```bash
docker compose --profile dev stop n8n
# Or skip --profile dev entirely:
docker compose down
docker compose up -d   # only postgres + api + frontend
```

Restart the backend so it re-reads the env:

```bash
docker compose restart api
docker compose logs api --tail 20
# Expect no startup errors
```

Smoke test from local backend → external n8n:

```bash
# Replace with a real webhook URL on your n8n
curl -fsS -X POST https://n8n.yourdomain.com/webhook/test-ping \
  -H "Content-Type: application/json" \
  -d '{"hello":"world"}'
```

Smoke test from external n8n → backend ingest:

In n8n editor, create a test workflow with one HTTP Request node:
- Method: POST
- URL: `={{ $env.API_BASE_URL }}/api/ingest/{{supplier_id}}/products`
- Headers: `X-Ingest-Secret: ={{ $env.INGEST_SHARED_SECRET }}`
- Body: `[]`

Execute. Expected: 200 (or empty-batch handling) — anything other than 401 means the secret is matched.

### 3B — Production / staging (CFN)

Edit `deployment/ecs/api-hub.yaml`. In `BackendTaskDef → ContainerDefinitions[0] → Environment` (around lines 487-501):

```yaml
- Name: N8N_API_BASE_URL
  Value: 'https://n8n.yourdomain.com'
- Name: N8N_WEBHOOK_BASE_URL
  Value: 'https://n8n.yourdomain.com'
- Name: N8N_PUSH_WEBHOOK_URL
  Value: 'https://n8n.yourdomain.com/webhook/vg-ops-push-001'
```

If you want these to vary per environment (staging vs production), promote them to CFN parameters:

```yaml
Parameters:
  N8nBaseUrl:
    Type: String
    Description: Base URL of the external n8n instance
  N8nPushWebhookPath:
    Type: String
    Default: /webhook/vg-ops-push-001
```

Then reference in the task def:

```yaml
- Name: N8N_API_BASE_URL
  Value: !Ref N8nBaseUrl
- Name: N8N_WEBHOOK_BASE_URL
  Value: !Ref N8nBaseUrl
- Name: N8N_PUSH_WEBHOOK_URL
  Value: !Sub '${N8nBaseUrl}${N8nPushWebhookPath}'
```

And add to `deployment/ecs/parameters/staging.json`:

```json
{"ParameterKey": "N8nBaseUrl", "ParameterValue": "https://n8n.yourdomain.com"}
```

### 3C — Drop the in-cluster n8n service (if using external)

If you're using external n8n exclusively and don't want a Fargate n8n, remove from `deployment/ecs/api-hub.yaml`:

- The whole `N8nTaskDef`, `N8nServiceDiscovery`, `N8nService` resource blocks
- The `N8nTargetGroup`, `N8nListenerRule`, `N8nDnsRecord` blocks if you don't want `n8n.<domain>` mapping
- `N8nTaskRole`, `N8nEfs`, `N8nEfsAccessPoint`, `N8nEfsMountTargetA/B`, `EfsSg`
- `N8nLogGroup`
- `N8nImageUri` parameter
- `N8nServiceName` output

Net deletion ~150 lines. Saves ~$25/mo (Fargate task + EFS + ALB target group).

---

## Phase 4 — Master options ingest (one-time per environment)

Master options live in OPS, not in API-HUB. The `master-options-pull-001` workflow in n8n pulls them and POSTs to `/api/ingest/master-options`. Run once after first cutover:

1. n8n editor → Workflows → `master-options-pull-001` → Execute Workflow (manual)
2. Watch the execution log; verify it returns 200 from the ingest endpoint
3. Confirm in backend:
   ```bash
   docker compose exec postgres psql -U vg_user -d vg_hub -c \
     "SELECT COUNT(*) FROM master_options;"
   # Expect non-zero
   ```

Activate the workflow if you want it to run on a cron schedule.

---

## Phase 5 — Smoke test the full push pipeline

End-to-end check that backend ↔ external n8n ↔ OPS works:

```bash
# 1. Pick a customer + product
# 2. Trigger push (use cookie auth, replace TOKEN)
curl -isS -X POST https://api.yourdomain.com/api/push/<customer_id>/<product_id> \
  -b "auth_token=<TOKEN>"
```

Expected response: `202` + `{"status":"pending", "push_log_id":"...", "payload":{...}}`

Then verify in n8n editor → Executions → look for the just-fired webhook execution. Should show OPS GraphQL call succeeding.

Check `push_log` in DB:
```sql
SELECT product_id, customer_id, status, ops_product_id, error
FROM product_push_log
ORDER BY pushed_at DESC LIMIT 5;
```

If `status='failed'`, the `error` column shows what n8n returned. If `status='pending'` forever, the n8n webhook URL is wrong or unreachable.

---

## Common failures + fixes

### Backend logs: `RuntimeError: N8N_PUSH_WEBHOOK_URL is required in production`

`ENVIRONMENT=production` and the env var is unset. Set it on the backend (not on n8n).

### Backend logs: `httpx.ConnectError` when triggering a push

Backend can't reach the n8n URL. Check:
- DNS resolves: `dig +short n8n.yourdomain.com`
- TLS valid: `curl -fsSI https://n8n.yourdomain.com/healthz`
- If backend is in VPC and n8n is public, NAT gateway / egress route must exist

### n8n logs: `401 Unauthorized` calling `/api/ingest/...`

`INGEST_SHARED_SECRET` mismatch. Both sides must hold the exact same value (no leading/trailing whitespace, no quotes).

### n8n editor doesn't show OnPrintShop node

Community node didn't load. Check:
- Self-hosted: container logs for `Loaded community node 'n8n-nodes-onprintshop'`
- n8n.cloud: Settings → Community Nodes → status of the OnPrintShop entry
- Node version compatible with running n8n version

### `client_secret` is shipped in plaintext webhook payloads

Acknowledged tradeoff (spec D15). Mitigations:
- Always HTTPS between backend and n8n
- Restrict n8n to only listen on private network if possible
- V2 follow-up: move OPS credentials to AWS Secrets Manager and have n8n read directly via IAM

### Cron workflow stops firing

n8n must be activated AND running. On hibernating platforms (Render Free), n8n sleeps after inactivity → cron misses fire windows. Use a paid tier with always-on, or switch the cron to AWS EventBridge calling backend directly.

---

## Workflow inventory

What ships in `n8n-workflows/`:

| File | Purpose | Trigger |
|---|---|---|
| `master-options-pull-001.json` | Pull master options from OPS | Manual / cron |
| `vg-ops-push-001.json` | Push product to customer OPS storefront | Webhook (from backend) |
| `catalog-sync-weekly.json` | Pull all suppliers' catalogs | Cron weekly |
| `sanmar-sftp-pull.json` | Pull SanMar bulk product feed via SFTP | Cron |
| ... others | | |

Every workflow:
- Reads from `$env.API_BASE_URL` for the backend URL
- Sends `X-Ingest-Secret: $env.INGEST_SHARED_SECRET` header
- Has retry + backoff configured per node

---

## Migration from local Docker n8n

If you've been running the bundled `n8n` service and want to move workflows + credentials to the external n8n:

1. Local: `docker compose --profile dev up -d n8n`
2. Local n8n editor → Workflows → Download All Workflows (zip)
3. Local n8n credentials: harder — the bundled n8n encrypts them with a generated `N8N_ENCRYPTION_KEY`. Export via CLI:
   ```bash
   docker compose exec n8n n8n export:credentials --backup --output=/tmp/creds.json
   docker compose cp n8n:/tmp/creds.json ./local-creds.json
   ```
4. External n8n: import workflows via UI, then for credentials either:
   - Use the same `N8N_ENCRYPTION_KEY` env var on the external host (keys must match) and run `n8n import:credentials --input=local-creds.json`
   - Or recreate credentials manually in the external n8n UI (simpler if there are only a few)

---

## Decommission the bundled n8n

Once the external n8n is the canonical source:

1. Stop and remove the local n8n container + image:
   ```bash
   docker compose --profile dev rm -fsv n8n
   docker rmi api-hub-n8n:dev   # if using the dev image tag
   ```
2. Remove the n8n volume if you don't need its data:
   ```bash
   docker volume rm api-hub_n8n_data
   ```
3. Optionally drop the `n8n` service from `docker-compose.yml` entirely. The `--profile dev` gate already keeps it out of `docker compose up` by default.

The custom `n8n.Dockerfile` stays in the repo — it's the source for the external Docker image too.

---

## Open questions for ops

- Where will external n8n live? (n8n.cloud Pro vs self-hosted?)
- Who owns the n8n editor login + API key rotation?
- Is OnPrintShop community node ever going to be published to npm? (would simplify install)
- Do we need cross-region n8n (active/passive) for DR? (V2)
