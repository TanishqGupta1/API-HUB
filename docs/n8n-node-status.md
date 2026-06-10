# n8n OnPrintShop Node — Status Decision

**Decision (2026-06-08): Keep as documented legacy fallback. Do not actively maintain for new push flows.**

## Background

The `n8n-nodes-onprintshop/` custom n8n node implements 40/40 OPS GraphQL mutations
and was the original mechanism for pushing products to OPS storefronts.

Post-M1, the FastAPI Integration Gateway (`modules/ops_push/gateway.py`) owns all
OPS push logic directly. n8n is now a trigger/orchestrator only — it calls the
FastAPI gateway via webhook, and the gateway executes mutations via
`modules/ops_client/`. The n8n node's mutation implementations are no longer in the
production push path.

## Current role

| Component | Role |
|-----------|------|
| `n8n-workflows/ops-inline-push.json` | Triggers FastAPI gateway via HTTP — **active** |
| `n8n-nodes-onprintshop/` | Legacy 40-mutation OPS node — **not in active push path** |

## Decision rationale

- Dual-maintaining the node + gateway creates divergence risk (mutation schemas drift)
- The node was kept "just in case" but has had zero production callers since M1 landed
- 40-mutation coverage is fully replicated in `_MUTATION_DISPATCH` + `_SET_*` constants
- Keeping it as a documented fallback costs nothing; actively maintaining it costs engineering time

## What this means in practice

- **Do not update** the node when OPS GraphQL schema changes — update `mutations.py` only
- **Do not add** new mutations to the node — add to `_SET_*` constants + `_MUTATION_DISPATCH`
- The node may be removed in a future cleanup once the team is confident the gateway is stable
- If a use case arises that genuinely needs the node (e.g. n8n-native flows outside API-HUB),
  document it as a new requirement rather than assuming the node is maintained

## Files

- `n8n-nodes-onprintshop/` — legacy node source (TypeScript)
- `n8n-workflows/ops-inline-push.json` — active trigger workflow (calls FastAPI)
- `modules/ops_client/mutations.py` — authoritative OPS query constants
- `modules/ops_push/gateway.py` — authoritative push orchestrator
