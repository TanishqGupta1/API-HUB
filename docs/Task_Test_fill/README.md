# Task Test Documentation

This folder contains test documentation for each completed task in API-HUB.
Each file explains what the task built and shows the exact commands to test it.

## Vidhi — Old Sprint Tasks (OPS Node + Push Pipeline)

| File | Task | Status |
|------|------|--------|
| [Task_1_setProduct_Mutation.md](Task_1_setProduct_Mutation.md) | `setProduct` mutation added to OPS n8n node | ✅ Done — merged to main |
| [Task_2_setProductSize_Mutation.md](Task_2_setProductSize_Mutation.md) | `setProductSize` mutation added to OPS n8n node | ✅ Done — merged to main |
| [Task_3_setProductCategory_Mutation.md](Task_3_setProductCategory_Mutation.md) | `setProductCategory` mutation added to OPS n8n node | ✅ Done — merged to main |
| [Task_4_OPS_Gap_Analysis_Update.md](Task_4_OPS_Gap_Analysis_Update.md) | Update `OPS-NODE-GAP-ANALYSIS.md` | ✅ Done — merged to main |
| Task 5 — n8n smoke test | Live OPS + SanMar smoke test | 🔴 Blocked — needs OPS OAuth2 + SanMar creds from Christian |
| [Task_6_Fix_OPS_Push_Workflow.md](Task_6_Fix_OPS_Push_Workflow.md) | Fix `ops-push.json` (category + size loop + error branch + `product_id` param) | ✅ Done — merged to main |
| [Task_7_Push_History_Component.md](Task_7_Push_History_Component.md) | Build `push-history.tsx` component | ✅ Done — superseded by main's simpler version after reshuffle |
| [Task_8_Wire_N8N_Trigger.md](Task_8_Wire_N8N_Trigger.md) | Wire real n8n trigger in Push Now button | ✅ Done — superseded by main's `PublishButton` after reshuffle |
| [Task_9_NextJS_Scaffold_Review.md](Task_9_NextJS_Scaffold_Review.md) | Code review: Sinchana's Next.js Scaffold (V0 Task 9) | ✅ Done — full review at `docs/09_Task9_Review.md` |

> **Superseded** = work was correct and merged, but the team reshuffle on 2026-04-23 restructured main's architecture. Your code was replaced by main's cleaner versions during conflict resolution. The task docs here are the permanent record.

## Vidhi — New Sprint Tasks (Demo Push Pipeline)

| Task | Description | Status |
|------|-------------|--------|
| New Task 4 | `GET /api/push/{customer_id}/product/{product_id}/ops-options` backend endpoint | 🔴 Blocked — needs Sinchana's Task 2 (push_mappings schemas) |
| New Task 5 | `ops-push.json` n8n workflow — add 4 new nodes | 🔴 Blocked — needs Sinchana's Task 3 (POST /api/push-mappings) |
| New Task 6 | Frontend: per-row "Push to OPS" dialog on `/products` catalog | ✅ Unblocked — start now |

## Other Team Tasks (V0 Plan)

| File | Task | Status |
|------|------|--------|
| [Task_14_4Over_HMAC_Client.md](Task_14_4Over_HMAC_Client.md) | 4Over REST + HMAC Client | ✅ Tested (9/9 unit tests; E2E blocked on sandbox creds) |
| [Task_15_4Over_Normalizer.md](Task_15_4Over_Normalizer.md) | 4Over Normalizer (raw JSON → PSProductData) | ✅ Tested (7/7 unit tests + 9 Task 14 regression tests) |
| [Task_16_Field_Mapping.md](Task_16_Field_Mapping.md) | Field Mapping Page | ✅ Tested |
| [Task_18_Customer_Model.md](Task_18_Customer_Model.md) | Customer Model (OAuth2) | ✅ Tested |
| [Task_19_Markup_Rules.md](Task_19_Markup_Rules.md) | Markup Rules | ✅ Tested |
| [Task_20_Push_Log.md](Task_20_Push_Log.md) | Push Log | ✅ Tested |

## Before Running Any Tests

Make sure Postgres is running and the backend is up:

```bash
cd "$(git rev-parse --show-toplevel)"
docker compose up -d postgres
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8001
```

All curl commands below assume the backend is running on `http://localhost:8001`.
