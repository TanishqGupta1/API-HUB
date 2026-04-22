# Tanishq — Sprint Tasks

**Sprint:** OPS Push Pipeline  
**Role:** PM / reviewer — no coding tasks this sprint

---

## Responsibilities

1. **Review every incoming PR** against the spec and the ops-push plan. Acceptance criteria in each person's task file.
2. **Merge order:** Sinchana Task 1 (types) before Vidhi Task 7 (PushHistory). Urvashi Task 2 (schemas) before Urvashi Task 3 (candidates). Otherwise parallel merges are safe.
3. **Chase credentials** (blocking E2E):
   - OPS customer `ops_auth_config` (Client ID + Secret) — needed for C2 E2E test
   - SanMar API credentials — needed for V1a Task 6 E2E
   - S&S API credentials — needed for V1b E2E
   - 4Over API credentials — needed for V1d E2E
   - **OPS Postman collection export** — export from browser, needed to verify exact GraphQL input typenames before C2
4. **After all Tier 1 PRs merged:** run C2 manual E2E (single product push through n8n → OPS), C3 error path test. Steps in `docs/superpowers/plans/2026-04-20-ops-push.md` Tasks C2 + C3.
5. **Write C4** operator guide `n8n-workflows/PUSH_README.md` once C2 passes.
6. **Scope keeper** — push back on anything not in `docs/superpowers/specs/2026-04-22-remaining-tasks-design.md`.

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
- [ ] Tanishq — C2 E2E manual push test (requires OPS creds)
- [ ] Tanishq — C3 error path test
- [ ] Tanishq — C4 PUSH_README.md
