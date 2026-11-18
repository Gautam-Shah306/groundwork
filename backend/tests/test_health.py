"""Tests for health endpoint and configuration loading."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_returns_ok() -> None:
    settings = Settings(
        _env_file=None,
        llm_api_key="",
        database_url="sqlite:///./data/groundwork.db",
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == settings.app_version
    assert payload["database_url_scheme"] == "sqlite"
    assert "groundwork.db" not in response.text


def test_health_reports_llm_not_configured_when_key_empty() -> None:
    settings = Settings(_env_file=None, llm_api_key="   ")
    client = TestClient(create_app(settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["llm_configured"] is False


def test_health_reports_llm_configured_when_key_set() -> None:
    settings = Settings(_env_file=None, llm_api_key="test-secret-key-123")
    client = TestClient(create_app(settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["llm_configured"] is True


def test_health_never_exposes_api_key() -> None:
    secret_key = "super-secret-llm-api-key-98765"
    secret_db_url = "postgresql://admin:supersecretpass@db.internal:5432/groundwork"
    settings = Settings(
        _env_file=None,
        llm_api_key=secret_key,
        database_url=secret_db_url,
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    body_text = response.text
    payload = response.json()
    assert secret_key not in body_text
    assert "supersecretpass" not in body_text
    assert "db.internal" not in body_text
    assert "llm_api_key" not in payload
    assert payload["database_url_scheme"] == "postgresql"


def test_config_defaults_load_without_env(monkeypatch, tmp_path) -> None:
    for var in (
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_MODEL",
        "DATABASE_URL",
        "CORS_ORIGINS",
        "APP_VERSION",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)

    settings = Settings(_env_file=None)

    assert settings.llm_provider == "gemini"
    assert settings.llm_api_key == ""
    assert settings.llm_model == "gemini-2.5-flash"
    assert settings.database_url == "sqlite:///./data/groundwork.db"
    assert settings.llm_configured is False
    assert settings.database_url_scheme == "sqlite"
    assert settings.cors_origin_list == ["http://localhost:5173"]


def test_app_starts_without_llm_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)

    application = create_app()
    with TestClient(application) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["llm_configured"] is False
