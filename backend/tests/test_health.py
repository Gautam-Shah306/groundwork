"""Tests for health endpoint and configuration loading."""

from fastapi.testclient import TestClient

from app.config import Settings, get_project_root
from app.main import create_app


def test_health_returns_ok(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        llm_api_key="",
        llm_model="",
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
        llm_model="gemini-2.5-flash",
        database_url=f"sqlite:///{tmp_path.as_posix()}/health_empty.db",
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["llm_configured"] is False


def test_health_reports_llm_not_configured_when_model_empty_or_provider_unsupported(
    tmp_path,
) -> None:
    no_model = Settings(
        _env_file=None,
        llm_provider="gemini",
        llm_api_key="test-secret-key-123",
        llm_model="  ",
        database_url=f"sqlite:///{tmp_path.as_posix()}/health_nomodel.db",
    )
    assert TestClient(create_app(no_model)).get("/api/health").json()["llm_configured"] is False

    bad_provider = Settings(
        _env_file=None,
        llm_provider="unsupported-vendor",
        llm_api_key="test-secret-key-123",
        llm_model="some-model",
        database_url=f"sqlite:///{tmp_path.as_posix()}/health_badprov.db",
    )
    assert (
        TestClient(create_app(bad_provider)).get("/api/health").json()["llm_configured"]
        is False
    )


def test_health_reports_llm_configured_when_key_set(tmp_path) -> None:
    settings = Settings(
        _env_file=None,
        llm_provider="gemini",
        llm_api_key="test-secret-key-123",
        llm_model="gemini-2.5-flash",
        database_url=f"sqlite:///{tmp_path.as_posix()}/health_set.db",
    )
    client = TestClient(create_app(settings))

    response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["llm_configured"] is True


def test_health_never_exposes_api_key(tmp_path) -> None:
    secret_key = "super-secret-llm-api-key-98765"
    secret_model = "private-model-id-54321"
    secret_db_url = "postgresql://admin:supersecretpass@db.internal:5432/groundwork"
    settings = Settings(
        _env_file=None,
        llm_api_key=secret_key,
        llm_model=secret_model,
        database_url=secret_db_url,
    )
    app_settings = Settings(
        _env_file=None,
        llm_api_key=secret_key,
        llm_model=secret_model,
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
    assert secret_model not in body_text
    assert "supersecretpass" not in body_text
    assert "db.internal" not in body_text
    assert "llm_api_key" not in payload
    assert "llm_model" not in payload
    assert payload["database_url_scheme"] == "postgresql"


def test_config_defaults_load_without_env(monkeypatch, tmp_path) -> None:
    for var in (
        "LLM_PROVIDER",
        "LLM_API_KEY",
        "LLM_MODEL",
        "LLM_TIMEOUT_SECONDS",
        "LLM_MAX_RETRIES",
        "LLM_MAX_OUTPUT_TOKENS",
        "LLM_REASONING_EFFORT",
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
    assert settings.llm_model == ""
    assert settings.llm_timeout_seconds == 60
    assert settings.llm_max_retries == 2
    assert settings.llm_max_output_tokens == 2500
    assert settings.llm_discovery_max_output_tokens == 6000
    assert settings.llm_triage_max_output_tokens == 2000
    assert settings.llm_reasoning_effort == "low"
    assert settings.database_url == "sqlite:///./data/groundwork.db"
    assert settings.llm_configured is False
    assert settings.database_url_scheme == "sqlite"
    assert settings.cors_origin_list == ["http://localhost:5173"]
    assert settings.seed_on_start is False


def test_discovery_max_output_tokens_default_is_6000() -> None:
    settings = Settings(_env_file=None)
    assert settings.llm_discovery_max_output_tokens == 6000


def test_eval_settings_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.eval_pacing_seconds == 2
    assert settings.eval_max_rate_limit_waits == 3
    assert settings.eval_max_wait_seconds == 120


def test_app_starts_without_llm_key(monkeypatch, tmp_path) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path.as_posix()}/startup_test.db")
    monkeypatch.chdir(tmp_path)

    application = create_app()
    with TestClient(application) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["llm_configured"] is False


def test_production_app_has_no_dependency_overrides() -> None:
    application = create_app()
    assert len(application.dependency_overrides) == 0
    custom_settings = Settings(_env_file=None)
    app_with_custom = create_app(custom_settings)
    assert len(app_with_custom.dependency_overrides) == 0


def test_llm_timeout_default_is_consistent_across_settings() -> None:
    """Test that LLM_TIMEOUT_SECONDS default is 60 in Settings, .env.example, docker-compose, and docs."""
    settings = Settings(_env_file=None)
    assert settings.llm_timeout_seconds == 60

    root = get_project_root()
    env_example = (root / ".env.example").read_text(encoding="utf-8")
    assert "LLM_TIMEOUT_SECONDS=60" in env_example

    compose = (root / "docker-compose.yml").read_text(encoding="utf-8")
    assert "LLM_TIMEOUT_SECONDS:-60" in compose

    docs_agent = (root / "docs/agent.md").read_text(encoding="utf-8")
    assert "`LLM_TIMEOUT_SECONDS` (default `60` s)" in docs_agent
