# Urvashi — Sprint Tasks

**Sprint:** Demo Push Pipeline (VG team demo)
**Spec:** `docs/superpowers/specs/2026-04-23-demo-push-pipeline-design.md`
**Full plan:** `docs/superpowers/plans/2026-04-23-demo-push-pipeline.md` (Task 7)
**Branch per task:** `urvashi/<task-slug>` → one PR per task

---

## Overview

1 task — SanMar SOAP ingestion setup. Light load this sprint: most heavy lifting is Sinchana (backend foundation) + Vidhi (endpoint + n8n + frontend).

Your work is **operational / data setup**, not new code. SanMar SOAP connector already ships from your earlier `fix/onprintshop-nodes` work (`backend/modules/promostandards/client.py` + `backend/scripts/sanmar_smoke.py`).

Depends on: none — can start any time. Blocks: Task 8 (E2E demo — needs products in hub).

Pre-work: same merge-conflict resolution as rest of team.

---

## Task 7 — Ingest 5–10 SanMar products via SOAP

**Files:** none to commit. Operations + data setup only.

Full plan → Task 7 → Steps 1–4.

### Step 1 — Verify SanMar SOAP supplier row exists

```bash
docker compose exec -T postgres psql -U vg_user -d vg_hub -c \
  "SELECT name, slug, protocol, base_url FROM suppliers WHERE slug = 'sanmar';"
```

If missing, create via:
```bash
curl -X POST http://localhost:8000/api/suppliers \
  -H "Content-Type: application/json" \
  -d '{
    "name": "SanMar",
    "slug": "sanmar",
    "protocol": "soap",
    "promostandards_code": "SANMAR",
    "base_url": "https://ws.sanmar.com:8080/SanMarWebService/SanMarWebServicePort",
    "auth_config": {
      "id": "<SANMAR_ID>",
      "password": "<SANMAR_PASSWORD>",
      "customer_number": "<SANMAR_CUSTNO>"
    }
  }'
```

Creds available from Tanishq. Tanishq has SanMar SOAP creds in hand per latest meeting.

### Step 2 — Run SanMar smoke script locally

```bash
cd backend && source .venv/bin/activate && python scripts/sanmar_smoke.py --limit 10
```

Expected output: 10 products printed with live pricing + inventory. No SOAP faults.

Script already exists in repo (`backend/scripts/sanmar_smoke.py`) from your prior work.

If faults — check credentials, SanMar SOAP endpoint URL, network access.

### Step 3 — Run n8n sanmar-soap-pull workflow

Open n8n UI (`http://localhost:5678`). Find `SanMar SOAP → Hub` workflow (from `n8n-workflows/sanmar-soap-pull.json`).

Confirm or set the STYLE# list to 10 styles. Suggested (common SanMar SKUs):
```
["PC61", "PC54", "ST350", "DT6100", "G200", "PC78", "K500", "L500", "PC90H", "PC55"]
```

Attach credentials. Execute manually. Verify workflow turns green.

### Step 4 — Verify products landed in hub

```bash
SANMAR_ID=$(curl -s "http://localhost:8000/api/suppliers" | python3 -c \
  "import sys,json; print(next(s['id'] for s in json.load(sys.stdin) if s['slug']=='sanmar'))")

curl -s "http://localhost:8000/api/products?supplier_id=$SANMAR_ID&limit=20" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'count={len(d)}'); \
    [print(f'  {p[\"supplier_sku\"]:8} {p[\"product_name\"][:50]:50} price={p[\"price_min\"]}-{p[\"price_max\"]}') for p in d]"
```

Expected: count=10, each row has a real SanMar style number + live price range.

### Step 5 — Open products in /products UI

`http://localhost:3000/products` — confirm 10 SanMar products visible, brand + price + inventory populated. This is what Vidhi's per-row Push button will hit in the demo.

**No commit — this is data setup. Document any issues encountered in a comment or Slack note for Tanishq.**

---

## Acceptance

10 SanMar products in hub DB with live SOAP pricing. Visible at `/products`. Ready for Vidhi's Task 6 (Push button) + Task 8 (E2E demo run by Tanishq).

---

## Files You Own

None modified. Only data in DB.

## Reused utilities

- `backend/modules/promostandards/client.py` — your existing SanMar SOAP client
- `backend/scripts/sanmar_smoke.py` — your existing smoke test script
- `n8n-workflows/sanmar-soap-pull.json` — existing workflow

## Why this task is light for you this sprint

You carried backend-heavy load last sprint (push_candidates, variant bundle, category OPS input, REST protocol dispatch, plus SanMar SOAP client patches + smoke script). This sprint shifts that weight to Sinchana + Vidhi so they can ship the demo plumbing while you stay available for SanMar issue triage if anything breaks during the E2E run.

If you finish Task 7 quickly and want more: pick up any failing tests, help Sinchana with her Task 3 tests, or triage any SOAP faults that surface during Tanishq's E2E run.
