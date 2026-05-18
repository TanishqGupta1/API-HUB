# Milestone Plan T9 — SanMar → OPS End-to-End Smoke Test

## What this task is

**Backend only.** T9 adds a pytest smoke test that exercises the full push pipeline from a seeded SanMar product through to a dry-run OPS push, asserting each stage. It's the integration check for everything fixed in T4–T6.

---

## How it relates to the existing project

Before T9, the push tests in `tests/test_gateway_push_request.py` covered HTTP status codes and idempotency — but all of them mocked `run_preflight` to always return OK. They never tested that a real product with real markup rules actually passes preflight, and they never verified the `step_results` shape that T6 fixed.

T9 fills that gap by running the real preflight (except the two network-bound checks) and asserting the shape of every `step_results` entry after the push completes.

---

## What the test covers

**File:** `backend/tests/test_sanmar_ops_smoke.py`

### Fixtures

`smoke_scaffold` seeds everything the pipeline needs:
- Supplier: `protocol="promostandards"`, `has_decoration_overlay=False` (skips decoration check)
- Product: `supplier_sku="PC61-SMOKE"`, `product_name` set, `category="T-Shirts"`
- ProductVariant: `sku`, `color`, `size`, `base_price=3.99`, `inventory=120`
- Customer: all four OPS credential fields populated
- MarkupRule: `scope="all"`, `markup_pct=20%` — ensures markup check passes

`smoke_key` creates a live `IntegrationKey` so the `X-Orchestrator-Key` header passes auth.

Both fixtures clean up after themselves.

### Patched checks

Two preflight checks require live network and are mocked to return `pass`:
- `check_ops_oauth2_reachable` — would attempt a real OAuth2 token fetch
- `check_image_urls_reachable` — would HEAD-request image URLs

All other checks run for real:
- `check_base_price_set` ✓ — variant has `base_price=3.99`
- `check_markup_rule_resolves` ✓ — global rule exists
- `check_push_mappings_present` ✓ — product has no options, nothing to map
- `check_customer_ops_creds_present` ✓ — all four fields set
- `check_prefix_collision` ✓ — no `ops_query_fn` wired → soft-pass
- `check_required_fields` ✓ — name + sku + 1 variant present
- `check_decoration_attached` ✓ — `has_decoration_overlay=False`

### Test cases

| Test | What it asserts |
|------|----------------|
| `test_dry_run_push_returns_dry_run_pushed` | HTTP 202, `status="dry_run_pushed"`, `dry_run=True`, `supplier_sku` echoed |
| `test_dry_run_step_results_shape` | Every `step_results` entry has `step` (int), `mutation` (str), `status` (ok/failed), `ops_ids` (dict), `attempted_at` (str), `request_fingerprint` (str) — the T6 shape |
| `test_dry_run_plan_includes_set_product_and_set_product_size` | Mutations list contains both `setProduct` and `setProductSize` (1 variant = 1 size step) |
| `test_dry_run_set_product_step_returns_products_id` | `setProduct` step's `ops_ids` contains `products_id` (FakeOpsClient returns a stub ID) |
| `test_preflight_blocks_when_variant_has_no_price` | Setting `base_price=None` → 422 PREFLIGHT_BLOCKER |

---

## What was clarified during implementation

- `ProductVariant` columns are `color` and `size`, not `color_name`/`size_name`
- `push_log.ops_product_id` is only written for live pushes (`status="pushed"`), not dry runs — the fake products_id from FakeOpsClient stays in `step_results[0].ops_ids` only
- `check_prefix_collision` auto-passes when no `ops_query_fn` is injected — no mock needed

---

## How to run

```bash
cd backend && source .venv/bin/activate
pytest tests/test_sanmar_ops_smoke.py -v
# 5 passed in ~2s
```

---

## How it can be modified in the future

- **Add a live-push variant**: Replace `dry_run=True` with `dry_run=False` and mock the `RealOpsClient` to return stub IDs. Asserts `status="pushed"` and `push_log.ops_product_id` is set.
- **Add more variants**: Create 2–3 `ProductVariant` rows; assert the number of `setProductSize` steps equals the variant count.
- **Add options**: Create a `ProductOption` + push mapping row; assert `setAdditionalOption` appears in the mutations list.
