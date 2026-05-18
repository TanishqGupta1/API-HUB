import pytest


@pytest.fixture
def clean_env(monkeypatch):
    for key in (
        "ENVIRONMENT", "N8N_WEBHOOK_BASE_URL", "N8N_API_BASE_URL",
        "API_BASE_URL",
        "SECRET_KEY", "JWT_SECRET_KEY", "INGEST_SHARED_SECRET",
        "ALLOWED_ORIGINS", "POSTGRES_URL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_dev_mode_does_not_require_n8n_urls(clean_env, monkeypatch):
    """Dev mode must boot without N8N_WEBHOOK_BASE_URL or API_BASE_URL set."""
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "development")
    _require_prod_env()  # no exception


def test_production_mode_fails_when_api_base_url_missing(clean_env, monkeypatch):
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 44)
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 44)
    monkeypatch.setenv("INGEST_SHARED_SECRET", "x")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://u:p@h/d")
    # API_BASE_URL intentionally not set
    with pytest.raises(RuntimeError, match="API_BASE_URL"):
        _require_prod_env()


def test_production_mode_passes_when_all_set(clean_env, monkeypatch):
    from main import _require_prod_env
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "k" * 44)
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 44)
    monkeypatch.setenv("INGEST_SHARED_SECRET", "x")
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("POSTGRES_URL", "postgresql+asyncpg://u:p@h/d")
    monkeypatch.setenv("API_BASE_URL", "http://backend.api-hub.local:8000")
    _require_prod_env()  # no exception
