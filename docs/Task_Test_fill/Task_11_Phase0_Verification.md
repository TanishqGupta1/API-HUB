# Task 11 — Phase 0 Full Stack Verification

## What This Task Does

This is the final gate for Phase 0. After all 10 previous tasks are complete across all three team members (Urvashi: Tasks 1-4, Sinchana: Tasks 5-7, Vidhi: Tasks 8-10), this task runs a full verification to confirm nothing is broken before merging to `main`.

It has 5 checks:
1. Backend test suite passes
2. Frontend lint passes
3. Live stack smoke tests pass
4. No raw `console.error`/`console.warn` in shipped frontend
5. DB is clean (no leaked test rows)

---

## Current Status (2026-04-28)

**Task 11 is partially verified.** Vidhi's own tasks (8, 9, 10) all pass. Two checks are blocked on other team members completing their tasks first.

| Check | Status | Detail |
|-------|--------|--------|
| Backend pytest | ⚠️ PARTIAL | 65 pass / 110 errors (ConnectionRefusedError — pre-existing DB config issue, not from Phase 0 changes) |
| Frontend lint | ⚠️ PARTIAL | 4 pre-existing errors in other teams' files. 0 errors from Vidhi's changes |
| `console.error`/`console.warn` | ❌ BLOCKED | 17 found — waiting on Sinchana Task 7 (log util + replace calls) |
| API + Frontend smoke tests | ⏳ SKIPPED | Backend and frontend servers not running locally |
| DB clean (no leaked customers) | ✅ PASS | 0 sentinel rows in `customers` table |

---

## How to Run Full Verification (Run After All Tasks Merged)

### Prerequisites

Make sure all services are running:

```bash
cd "$(git rev-parse --show-toplevel)"
docker compose up -d postgres

# Terminal 1 — Backend
cd "$(git rev-parse --show-toplevel)/backend" && source .venv/bin/activate
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd "$(git rev-parse --show-toplevel)/frontend"
npm run dev
```

---

### Step 1 — Backend Test Suite

```bash
cd "$(git rev-parse --show-toplevel)/backend" && source .venv/bin/activate
pytest -q
```

**Expected:** all green, 0 errors, 0 failures.

---

### Step 2 — Frontend Lint + Build

```bash
cd "$(git rev-parse --show-toplevel)/frontend"
npm run lint
npm run build
```

**Expected:** lint exits 0 (no errors), build succeeds.

---

### Step 3 — Live Stack Smoke Tests

```bash
# API health
curl -sf http://127.0.0.1:8000/health

# Frontend up
curl -sI http://127.0.0.1:3000 | head -1

# push-log endpoint
curl -sf "http://127.0.0.1:8000/api/push-log?limit=1" > /dev/null && echo "push-log OK"

# push-status endpoint (needs a real product ID)
PRODUCT_ID=$(curl -s http://127.0.0.1:8000/api/products | python3 -c 'import sys,json;print(json.load(sys.stdin)[0]["id"])')
curl -sf "http://127.0.0.1:8000/api/products/$PRODUCT_ID/push-status" > /dev/null && echo "push-status OK"
```

**Expected:** all four commands succeed.

---

### Step 4 — Zero console.error/warn in Frontend

```bash
cd "$(git rev-parse --show-toplevel)/frontend"
grep -rn 'console\.\(error\|warn\)' src/ | grep -v 'src/lib/log.ts'
```

**Expected:** zero matches. (After Sinchana's Task 7 is done, all raw calls are replaced with `log.error`/`log.warn` via `src/lib/log.ts`.)

---

### Step 5 — DB Clean

```bash
cd "$(git rev-parse --show-toplevel)"
docker compose exec -T postgres psql -U vg_user -d vg_hub -c \
  "SELECT id, name, ops_base_url FROM customers
   WHERE ops_base_url IN (
     'https://test.ops.com',
     'https://test2.ops.com',
     'https://test3.ops.com'
   );"
```

**Expected:** `(0 rows)`.

---

## What Each Failure Means

| Failure | Root cause | Who fixes it |
|---------|-----------|--------------|
| pytest `ConnectionRefusedError` | Postgres not reachable from test runner / `.env` config | Urvashi Task 2 (TEST_DATABASE_URL wiring) |
| Lint error: unescaped `'` in JSX | Raw apostrophes in JSX strings need `&apos;` | File owner (Urvashi / Sinchana depending on file) |
| `console.error`/`warn` found | Task 7 not yet merged | Sinchana Task 7 |
| Push-log route 404 | Router prefix not normalized | Urvashi Task 3 |

---

## Verification Results — Vidhi's Scope Only (2026-04-28)

| Check | Result |
|-------|--------|
| Hardcoded paths removed (Task 8) | ✅ PASS — 0 matches in `docs/Task_Test_fill/` |
| Code review doc annotated (Task 9) | ✅ PASS — 9 status lines confirmed |
| DB clean (Task 10) | ✅ PASS — 0 leaked customer rows |
| No regressions from Vidhi's commits | ✅ PASS — all changed files are docs only |

**Full Task 11 sign-off is pending Urvashi Tasks 1-4 and Sinchana Tasks 5-7 merging to `main`.**
