# Tanishq — Sprint Tasks

**Sprint:** OPS Push Pipeline + SanMar SFTP  
**Role:** PM / reviewer

---

## Responsibilities

1. **Review every incoming PR** against the spec and acceptance criteria in each person's task file.
2. **Merge order:** Sinchana Task 1 (types) before Vidhi Task 7 (PushHistory). Urvashi Task 2 (schemas) before Urvashi Task 3 (candidates). SanMar: Vidhi D1→D2→W1→W2 sequential; Sinchana W4 parallel.
3. **Scope keeper** — push back on anything not in `docs/superpowers/specs/2026-04-22-remaining-tasks-design.md` or `docs/superpowers/specs/2026-04-22-sanmar-sftp-integration-design.md`.

---

## Tanishq's Own Tasks (essential only)

### OPS Push

- **C2** — Manual E2E: single product push through n8n → OPS. Steps in `docs/superpowers/plans/2026-04-20-ops-push.md` Task C2. *(Requires OPS creds + all Tier 1 PRs merged)*
- **C3** — Error path test. Steps in ops-push plan Task C3.
- **C4** — Write `n8n-workflows/PUSH_README.md` operator guide.

### SanMar SFTP (credential-gated — do these first, unblocks Vidhi)

- **P1** — Create SanMar supplier DB row:
  ```bash
  curl -X POST http://localhost:8000/api/suppliers \
    -H "Content-Type: application/json" \
    -d '{"name":"SanMar","slug":"sanmar","protocol":"sftp","auth_config":{}}'
  ```
  Save the returned `id`.

- **P2** — Add `SanMar SFTP` credential in n8n UI:
  - Settings → Credentials → New → SFTP
  - Host: `ftp.sanmar.com`, Port: `2200`, Username + Password from Christian

- **P3** — Set `INGEST_SHARED_SECRET` in n8n environment variables (match value from `api-hub/.env`)

- **E1** — After Vidhi's W1+W2 merged: run full SFTP workflow, verify products in DB:
  ```bash
  curl "http://localhost:8000/api/products?supplier_id=<sanmar_id>&limit=5" | python3 -m json.tool
  ```

### Credentials to chase from Christian

- [ ] SanMar SFTP username + password *(have host/port, need user/pass)*
- [ ] OPS customer `ops_auth_config` (Client ID + Secret) — needed for C2
- [ ] OPS Postman collection export — needed for GraphQL input typenames
- [ ] S&S API credentials
- [ ] 4Over API credentials

---

## PR Review Checklist

For every PR:
- [ ] File ownership respected (no one edited someone else's files)
- [ ] Blueprint design system followed on frontend PRs (paper `#f2f0ed`, blue `#1e4d92`, shadcn/ui components)
- [ ] No `Co-Authored-By` lines in commits
- [ ] No per-supplier code or hardcoded credentials
- [ ] `VARCHAR` not PG ENUM for any new DB column type fields
- [ ] Backend: upserts use `ON CONFLICT DO UPDATE`, not plain `INSERT`

---

## Sprint Sign-Off Checklist

- [ ] Sinchana 1 — ProductPushLogRead type
- [ ] Sinchana 2 — Sync dashboard health
- [ ] Sinchana 3 — Terminology overhaul
- [ ] Sinchana 4 — Simplified supplier form
- [ ] Vidhi 1 — Customers (Storefronts) page
- [ ] Vidhi 2 — setProductSize OPS node (A3)
- [ ] Vidhi 3 — setProductCategory OPS node (A4)
- [ ] Vidhi 4 — Gap analysis doc update (A5)
- [ ] Vidhi 5 — n8n smoke test (A6, manual)
- [ ] Vidhi 6 — Verify ops-push.json (C1)
- [ ] Vidhi 7 — PushHistory component (D2)
- [ ] Vidhi 8 — PublishButton + wire (D3)
- [ ] Vidhi 9 — Workflows page (0.5)
- [ ] Urvashi 1 — Dashboard API wiring (0.6)
- [ ] Urvashi 2 — push_log schemas + POST (B1)
- [ ] Urvashi 3 — push_candidates module (B2)
- [ ] Urvashi 4 — Variant bundle endpoint (B4)
- [ ] Urvashi 5 — Category OPS input endpoint (B5)
- [ ] Urvashi 6 — Image pipeline cache header (B6)
- [ ] Urvashi 7 — Wire S&S/4Over protocols (G2)
- [ ] Urvashi 8 — Fix SanMar protocol in supplier form
- [ ] Urvashi 9 — Products API no-supplier filter
- [ ] Tanishq — C2 E2E manual push test (requires OPS creds)
- [ ] Tanishq — C3 error path test
- [ ] Tanishq — C4 PUSH_README.md
