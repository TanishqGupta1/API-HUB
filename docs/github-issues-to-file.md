# GitHub Issues to File

Run each block below with `gh issue create` once authenticated, or paste into GitHub UI.

---

## Issue 1 — [BLOCKER] setProduct returns 500 on OPS staging

**Labels:** `bug`, `blocker`, `ops-push`

```
gh issue create \
  --title "[BLOCKER] setProduct returns INTERNAL_SERVER_ERROR on OPS staging" \
  --body "## Summary
Every setProduct call to OPS staging returns HTTP 500 INTERNAL_SERVER_ERROR.
Same OAuth token successfully creates categories and runs productByFilter queries —
the failure is isolated to the setProduct resolver on the OPS Express server.

## Evidence
- Cloudflare Ray: a065c8cd38bdce12-SIN (2026-06-04 09:06:56 GMT)
- Category creation works, product creation fails
- See \`docs/ops-staging-setproduct-issue.md\` for full payload + response log

## Impact
Nothing lands in OPS until this is fixed — all downstream push steps (sizes,
prices, stock, images) are gated on a valid products_id from setProduct.

## Action needed
OPS team (Christian) to pull Express app-server log for the Ray ID above and
identify the resolver bug.

## Owner
OPS / Christian"
```

---

## Issue 2 — [HIGH] Silent failure: gateway records result:false as ok

**Labels:** `bug`, `high`, `ops-push`

```
gh issue create \
  --title "[HIGH] Gateway records OPS result:false as success (silent failure)" \
  --body "## Summary
When OPS returns HTTP 200 + \`result:false\` (application-layer rejection),
the gateway logs the step as \`ok\` and continues. This silently drops data.

## Known incidents
- PC54: phantom products_id 10001 — setProduct rejected, id:null treated as success
- PC61: 558 dropped prices — setProductPrice rejected on every variant

## Root cause
\`gateway.py _invoke\` returned \`data or {}\` with no rejection check.

## Status
Fix is in \`_check_result()\` (mutations.py) + \`OpsClientAdapter._invoke()\`.
Verify this is wired end-to-end and covered by CI.

## Owner
DEV"
```

---

## Issue 3 — [HIGH] Apparel variant model wrong (setAdditionalOption not wired)

**Labels:** `bug`, `high`, `ops-push`, `apparel`

```
gh issue create \
  --title "[HIGH] Apparel variants use setProductSize — OPS expects setAdditionalOption" \
  --body "## Summary
Apparel products currently push size variants via \`setProductSize\`.
OPS apparel products require \`setAdditionalOption\` + \`setAdditionalOptionAttributes\`
(ref OPS product 361). Products appear to push but are not properly shoppable.

## Detail
- \`OptionStrategy\` + builders exist in \`payload_builder.py\` but not wired for apparel
- Need to flip strategy routing in gateway for apparel product_type
- See \`docs/backlog-ops-additional-options.md\`

## Blocked on
Christian to confirm expected OPS field shape for apparel variants before switching.

## Owner
DEV (after Christian confirms)"
```

---

## Issue 4 — [MEDIUM] Images disabled (OPS_PUSH_INCLUDE_IMAGES=0)

**Labels:** `enhancement`, `medium`, `ops-push`

```
gh issue create \
  --title "[MEDIUM] Images disabled — OPS has no upload mutation, needs URL-fetch or upload API" \
  --body "## Summary
Image push is disabled by default (\`OPS_PUSH_INCLUDE_IMAGES=0\`).
OPS GraphQL stores \`products_large_image_name\` as a string verbatim —
it does not fetch URLs or accept binary uploads via the GraphQL API.

## To enable
Images must exist in OPS media first (admin URL-fetch or a REST upload endpoint).
Once OPS confirms an image ingestion path, flip the flag and wire the gallery step.

## Owner
OPS (Christian to confirm upload path) + DEV"
```

---

## Issue 5 — [MEDIUM] Stock disabled (OPS_PUSH_INCLUDE_STOCK=0)

**Labels:** `enhancement`, `medium`, `ops-push`

```
gh issue create \
  --title "[MEDIUM] Stock push disabled — requires OPS admin stock init + stock_id resolution" \
  --body "## Summary
Stock push is disabled by default (\`OPS_PUSH_INCLUDE_STOCK=0\`).
\`updateProductStock\` requires a \`stock_id\` which OPS only creates via admin UI —
there is no API to create initial stock entries.

## Implementation
\`_resolve_stock_id_for_size()\` in gateway.py reads back \`productStocks\` to resolve
the id. OPS admin must init stock entries before this can run.

## To enable
1. OPS admin creates initial stock entries for the product via UI
2. Set \`OPS_PUSH_INCLUDE_STOCK=1\`

## Owner
DEV + OPS (admin stock init)"
```
