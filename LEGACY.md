# Legacy / historical code

This file tracks code and docs moved to `historical/` rather than deleted, per
`_CANONICAL-AUTHORITY.md`: "Do not delete legacy docs — they capture real logic. Just don't treat
them as the spec."

## historical/2026-07/ — n8n removal (2026-07-21)

n8n was dropped as a built tier per `DECISIONS-LOG.md` (LOCKED 2026-06-30) — GraphX does not build
or embed n8n; API-HUB's own scheduler (`backend/modules/import_jobs/scheduler.py`) and Integration
Gateway (`backend/modules/integrations/`) now own scheduling and OPS push directly, in-process. The
following were moved here, unmounted, and are no longer built, run, or referenced by any live code
path:

| Moved item | Was | Original location |
|---|---|---|
| `n8n_proxy/` | The n8n workflow trigger pass-through module, mounted as `/api/n8n/*` (`vg_admin`-gated) | `backend/modules/n8n_proxy/` |
| `n8n-workflows/` | The n8n cron workflow JSON exports (catalog-sync-weekly, pricing-sync-daily, inventory-sync-hourly, closeouts-monthly, ops-push, ops-master-options-pull) | repo root |
| `n8n-nodes-onprintshop/` | The custom TypeScript n8n node for the OnPrintShop GraphQL API | repo root |
| `n8n.Dockerfile` | The Docker build for a self-hosted n8n instance with the OnPrintShop node baked in | repo root |
| `n8n-integration.md` | The n8n integration contract doc | `docs/` |
| `external-n8n-setup.md` | Setup instructions for a hosted (non-bundled) n8n instance | `docs/` |

Verified against `graphx-connect@dfbf27f`, 2026-07-21. n8n remains, at most, a possible future
*integration target* (a system Connect could integrate *to* if a tenant already runs one) per
`GraphXCPI/graphx-docs/atomic-specs/connect.md` §4.1 — never a built engine in this repo.
