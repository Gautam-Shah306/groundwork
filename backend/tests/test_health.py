"""Tests for health endpoint and configuration loading."""

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_returns_ok(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        llm_api_key="",
        database_url=f"sqlite:///{tmp_path.as_posix()}/health_ok.db",
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["version"] == settings.app_version
    assert payload["database_url_scheme"] == "sqlite"
    assert "health_ok.db" not in response.text


def test_health_reports_llm_not_configured_when_key_empty(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        llm_api_key="   ",
        database_url=f"sqlite:///{tmp_path.as_posix()}/health_empty.db",
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["llm_configured"] is False


def test_health_reports_llm_configured_when_key_set(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        llm_api_key="test-secret-key-123",
        database_url=f"sqlite:///{tmp_path.as_posix()}/health_set.db",
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["llm_configured"] is True


def test_health_never_exposes_api_key(tmp_path) -> None:
    secret_key = "super-secret-llm-api-key-98765"
    secret_db_url = "postgresql://admin:supersecretpass@db.internal:5432/groundwork"
    settings = Settings(
        _env_file=None,
        llm_api_key=secret_key,
        database_url=secret_db_url,
    )
    # Use a temporary SQLite DB for engine creation via state override if needed,
    # while checking that health reports only scheme and never leaks secrets.
    app_settings = Settings(
        _env_file=None,
        llm_api_key=secret_key,
        database_url=f"sqlite:///{tmp_path.as_posix()}/health_secret.db",
    )
    application = create_app(app_settings)
    application.state.settings = settings
    client = TestClient(application)

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
        "SEED_ON_START",
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
    assert settings.seed_on_start is False


def test_app_starts_without_llm_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/startup_test.db")
    monkeypatch.chdir(tmp_path)

    application = create_app()
    with TestClient(application) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["llm_configured"] is False
