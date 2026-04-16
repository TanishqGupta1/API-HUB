# Task Test Documentation

This folder contains test documentation for each completed task in API-HUB.
Each file explains what the task built and shows the exact commands to test it.

## Index

| File | Task | Status |
|------|------|--------|
| [Task_18_Customer_Model.md](Task_18_Customer_Model.md) | Customer Model (OAuth2) | ✅ Tested |
| [Task_19_Markup_Rules.md](Task_19_Markup_Rules.md) | Markup Rules | ✅ Tested |
| [Task_20_Push_Log.md](Task_20_Push_Log.md) | Push Log | ✅ Tested |
| [Task_16_Field_Mapping.md](Task_16_Field_Mapping.md) | Field Mapping Page | ✅ Tested |

## Before Running Any Tests

Make sure Postgres is running and the backend is up:

```bash
cd /Users/PD/API-HUB
docker compose up -d postgres
cd backend && source .venv/bin/activate
uvicorn main:app --reload --port 8001
```

All curl commands below assume the backend is running on `http://localhost:8001`.
