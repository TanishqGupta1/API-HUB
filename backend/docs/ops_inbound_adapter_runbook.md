# OPS Inbound Adapter — Operations Runbook

## What this gives you
- `OPSAdapter` reads OnPrintShop products via GraphQL (`listProducts`, `getProduct`, `listProductsModifiedSince`) and feeds them through the polymorphic `persist_product` from Phase 1.
- `POST /api/suppliers/{id}/import` queues an import job, returns a real `sync_job_id` immediately, and runs hydration in a FastAPI BackgroundTask.
- `GET /api/sync-jobs/{id}` (already shipped) lets the caller poll status.

## Configuring an OPS supplier
```sql
update suppliers
   set adapter_class = 'OPSAdapter',
       base_url      = 'https://<storefront>.onprintshop.com',
       auth_config   = jsonb_build_object('auth_token', '<bearer-token>')
 where id = '<supplier-uuid>';
```

## Triggering an import
```bash
curl -X POST http://localhost:8000/api/suppliers/$ID/import \
     -H 'content-type: application/json' \
     -d '{"mode": "first_n", "limit": 20}'
```

Modes:
- `explicit_list` — `{"mode": "explicit_list", "explicit_list": ["131", "262"]}`
- `first_n`       — `{"mode": "first_n", "limit": 20}`
- `full`          — `{"mode": "full"}`
- `delta`         — `{"mode": "delta"}` (uses `listProductsModifiedSince`)

## Status semantics
| Status | Meaning |
|--------|---------|
| `queued` | Endpoint accepted, BG task not started yet. |
| `running` | BG task in flight. |
| `success` | All products hydrated + persisted. `last_full_sync` / `last_delta_sync` updated. |
| `partial_success` | At least one product persisted; per-product errors in `sync_jobs.errors[]`. |
| `failed` | Auth error or zero products persisted. See `sync_jobs.errors[]`. |

## Concurrency
A second `POST /api/suppliers/{id}/import` for the same `(supplier, mode)` while the previous job is `queued` or `running` returns `409`.

## Rollback
- Code rollback only: revert this branch + restart. New tables/columns from Phase 1 stay in place (idempotent).
- The new `import_jobs` package and `ops_inbound` package are unused after rollback but harmless. Drop them only if you're sure no scheduled task or in-flight job references them.
