# Deprecated n8n Workflows

These workflows are kept for reference only. They are **no longer active** and should not be imported or run.

## ops-push.json

The n8n-based OPS push workflow. Superseded in Phase 8 by the Integration Gateway (`POST /api/integrations/v1/push-requests`), which runs the OPS mutation plan directly in FastAPI via `execute_push()`.

**Removed from active use:** 2026-05-15  
**Replacement:** `modules/ops_push/gateway.py` — `prepare_push_intent()` + `execute_push()`
