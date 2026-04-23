import os
import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from sqlalchemy import select, delete
from database import async_session


@pytest.fixture(autouse=True)
async def _cleanup():
    yield
    from modules.master_options.models import MasterOption
    async with async_session() as s:
        await s.execute(delete(MasterOption))
        await s.commit()


@pytest.mark.asyncio
async def test_ingest_master_options_upserts():
    secret = os.environ["INGEST_SHARED_SECRET"]
    payload = [
        {
            "ops_master_option_id": 501,
            "title": "Ink Finish",
            "option_key": "ink_finish",
            "options_type": "checkbox",
            "status": 1,
            "sort_order": 10,
            "attributes": [
                {"ops_attribute_id": 9001, "title": "Gloss", "sort_order": 1, "default_price": 0},
                {"ops_attribute_id": 9002, "title": "Matte", "sort_order": 2, "default_price": 0},
            ],
        }
    ]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/ingest/master-options",
            json=payload,
            headers={"X-Ingest-Secret": secret},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["records_processed"] == 1


@pytest.mark.asyncio
async def test_ingest_master_options_rejects_bad_secret():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/ingest/master-options",
            json=[],
            headers={"X-Ingest-Secret": "wrong"},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_master_options_returns_ingested():
    secret = os.environ["INGEST_SHARED_SECRET"]
    payload = [{
        "ops_master_option_id": 502,
        "title": "Print Sides",
        "options_type": "radio",
        "attributes": [
            {"ops_attribute_id": 9101, "title": "Single", "sort_order": 1},
            {"ops_attribute_id": 9102, "title": "Double", "sort_order": 2},
        ],
    }]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        await c.post("/api/ingest/master-options", json=payload, headers={"X-Ingest-Secret": secret})
        r = await c.get("/api/master-options")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    found = [m for m in data if m["ops_master_option_id"] == 502]
    assert found
    assert len(found[0]["attributes"]) == 2


@pytest.mark.asyncio
async def test_sync_status_reports_count():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.get("/api/master-options/sync-status")
    assert r.status_code == 200
    body = r.json()
    assert "total" in body
    assert "last_synced_at" in body
