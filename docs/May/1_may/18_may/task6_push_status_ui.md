# Milestone Plan T6 — Push Status UI

## What this task is

**Backend + Frontend.** T6 verifies that after a product is pushed to OPS, the admin sees a clear result — overall status, OPS product ID, per-step details, and error messages if anything failed.

---

## How it relates to the existing project

The push log detail page at `/push-log/[id]` already existed with:
- A status banner showing "Pushed to OPS" or "Dry-run complete"
- An `Execution Timeline` section showing each mutation step
- Per-step expandable panels with OPS IDs and request fingerprints

The `PushTimeline` component reads from `push_log.step_results` — a JSONB column the backend writes after each mutation runs.

The problem: `execute_push()` was writing `step_results` in one shape, but `PushTimeline` and the `OPSStepResult` TypeScript type expected a completely different shape.

---

## What was broken

### Backend writing wrong field names

`execute_push()` was writing:
```json
{
  "step": "setProduct",      ← mutation name string, not step number
  "ok": true,                ← boolean, frontend used "status"
  "ops_id": "12345",         ← singular string, frontend expected "ops_ids" object
  "called_at": "...",        ← frontend expected "attempted_at"
}
```

But `OPSStepResult` (TypeScript + Pydantic) expects:
```json
{
  "step": 1,                          ← number
  "source_key": "supplier_sku:PC61",  ← missing entirely
  "mutation": "setProduct",           ← missing entirely
  "request_fingerprint": "abc123...", ← missing entirely
  "ops_ids": {"products_id": 12345},  ← object, not string
  "attempted_at": "...",              ← correct field name
  "status": "ok"                      ← missing entirely
}
```

### `push_log.error` never set on failure

The push log detail page shows `log.error` in a red banner when status is `failed` or `partial_failure`. But `execute_push()` never set `push_log.error` — only the per-step `step_results` had the error message. So the red banner was always empty.

### Per-step error messages not shown in timeline

`PushTimeline` opened the expandable panel for failed steps but only showed the OPS IDs (empty dict on failure) and request fingerprint. The actual error string from OPS was never displayed.

---

## What changed

### `backend/modules/ops_push/gateway.py`

1. Imported `_request_fingerprint` from `payload_builder` to generate consistent 16-char step fingerprints.

2. Rewrote the step_results entry shape to match `OPSStepResult`:
```python
step_results.append({
    "step": step_num,
    "source_key": step.get("source_key", ""),
    "mutation": mutation,
    "request_fingerprint": _request_fingerprint(variables),
    "ops_ids": resp,
    "attempted_at": t_start.isoformat(),
    "status": "ok",
    "latency_ms": latency,
})
```

3. On failure, same shape but `"status": "failed"` and `"error": str(e)`.

4. After the execution loop, sets `push_log.error` when final status is `failed` or `partial_failure`:
```python
if final_status in ("failed", "partial_failure"):
    failed_step = next((s for s in step_results if s.get("status") == "failed"), None)
    if failed_step:
        push_log.error = f"{failed_step['mutation']}: {failed_step.get('error', 'unknown error')}"
```

### `frontend/src/lib/types.ts`

Updated `OPSStepResult`:
- `status` changed from optional `"ok" | "failed"` to required
- Added `error?: string | null`
- Added `latency_ms?: number`

### `frontend/src/components/push/PushTimeline.tsx`

1. Fixed `isOk` check: `step.status === "ok"` (was `step.status !== "failed"` — fails on undefined).

2. Added error message display for failed steps — shows above the JSON panels in red:
```tsx
{!isOk && step.error && (
  <div className="bg-[#fdf2f2] border border-[#b93232] rounded-lg px-4 py-3 font-mono text-[12px] text-[#7b1d1d]">
    <span className="font-bold text-[#b93232]">Error: </span>{step.error}
  </div>
)}
```

3. Added `latency_ms` to the request fingerprint panel so you can see how long each OPS call took.

---

## What the UI now shows after a push

**Success (`pushed`):**
- Green banner top-right: "Pushed to OPS · products_id = 12345"
- Timeline: each step has a green circle, step number, mutation name, `ok` pill, source key, OPS ID
- Expanded view: `ops_ids` object (e.g. `{"products_id": 12345}`), fingerprint, latency_ms

**Failure (`failed` / `partial_failure`):**
- Red banner at top-right (existing)
- Red error box below: "setProductPrice: OPS setProductPrice failed: [INVALID_INPUT] size_id is required"
- Timeline: failed step has red circle, auto-expanded with error message shown in red

**Dry run (`dry_run_pushed`):**
- Blue banner: "Dry-run complete · FakeOpsClient — no real writes"
- Timeline: all steps with fake IDs, latency_ms shows actual FakeOpsClient timing

---

## How it can be modified in the future

- **Add more step detail**: The `ops_ids` panel shows the raw OPS response. As more mutation types are added, their response fields will automatically appear here.
- **Add "View in OPS" link**: After a successful push, the `ops_product_id` on `PushLog` can be used to link directly to the product in OPS (`{ops_base_url}/products/{ops_product_id}`). The `ops_target.base_url` field on the payload has the URL.
- **SSE streaming**: The `PushTimeline` comment mentions Task 9 / SSE. When SSE is wired up, each step result can be streamed as it completes instead of polling every 2 seconds.
