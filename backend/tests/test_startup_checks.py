import os
import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture
def clean_env(monkeypatch):
    """Clear env vars the check looks for, restore after test."""
    for key in (
        "ENVIRONMENT", "SECRET_KEY", "JWT_SECRET_KEY",
        "INGEST_SHARED_SECRET", "ALLOWED_ORIGINS",
        "POSTGRES_URL", "N8N_WEBHOOK_BASE_URL", "API_BASE_URL",
    ):
        monkeypatch.delenv(key, raising=False)


async def test_dev_mode_passes_with_no_env(clean_env, monkeypatch):
    """Development mode must not fail on missing prod-only vars."""
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "development")
    _require_prod_env()  # no exception


async def test_production_mode_fails_when_secret_key_missing(clean_env, monkeypatch):
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("INGEST_SHARED_SECRET", "x")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://u:p@h/d")
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        _require_prod_env()


async def test_production_mode_passes_when_all_vars_set(clean_env, monkeypatch):
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 44)
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 44)
    monkeypatch.setenv("INGEST_SHARED_SECRET", "x")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("N8N_WEBHOOK_BASE_URL", "http://n8n.local:5678")
    monkeypatch.setenv("API_BASE_URL", "http://backend.local:8000")
    _require_prod_env()  # no exception
