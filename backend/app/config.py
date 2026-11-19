"""Application configuration loaded from environment variables."""

from pathlib import Path
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


def get_project_root() -> Path:
    """Resolve the root directory that owns ./data both natively and in Docker.

    Natively, this file lives at <repo>/backend/app/config.py so parents[1] is
    <repo>/backend and the repo root is parents[2] (verified by docker-compose.yml).
    Inside the backend Docker container, WORKDIR is /app with ./data mounted at
    /app/data, so parents[1] is /app.
    """
    app_parent = Path(__file__).resolve().parents[1]
    if app_parent.name == "backend" and (app_parent.parent / "docker-compose.yml").exists():
        return app_parent.parent
    return app_parent


def resolve_database_url(database_url: str) -> str:
    """Anchor relative sqlite:/// URLs to the shared project root directory."""
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        return database_url

    raw_path = database_url[len(prefix) :]
    if raw_path in ("", ":memory:") or raw_path.startswith("file:"):
        return database_url

    candidate = Path(raw_path)
    if candidate.is_absolute():
        candidate.parent.mkdir(parents=True, exist_ok=True)
        return f"{prefix}{candidate.as_posix()}"

    resolved = (get_project_root() / candidate).resolve()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return f"{prefix}{resolved.as_posix()}"


SUPPORTED_LLM_PROVIDERS: frozenset[str] = frozenset({"gemini", "groq"})


class Settings(BaseSettings):
    """Runtime settings with safe defaults so startup never requires an LLM key."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_version: str = "0.1.0"
    llm_provider: str = "gemini"
    llm_api_key: str = ""
    llm_model: str = ""
    llm_timeout_seconds: int = 30
    llm_max_retries: int = 2
    llm_max_output_tokens: int = 2500
    llm_discovery_max_output_tokens: int = 4000
    llm_reasoning_effort: str = "low"
    database_url: str = "sqlite:///./data/groundwork.db"
    cors_origins: str = "http://localhost:5173"
    seed_on_start: bool = False

    @property
    def llm_configured(self) -> bool:
        """Return whether a supported LLM provider, API key, and model are all configured."""
        return (
            self.llm_provider.strip().lower() in SUPPORTED_LLM_PROVIDERS
            and bool(self.llm_api_key.strip())
            and bool(self.llm_model.strip())
        )

    @property
    def database_url_scheme(self) -> str:
        """Return only the URL scheme for the database connection string."""
        parsed = urlparse(self.database_url)
        return parsed.scheme or "unknown"

    @property
    def resolved_database_url(self) -> str:
        """Return the normalized database URL anchored to the shared data directory."""
        return resolve_database_url(self.database_url)

    @property
    def resolved_config_dir(self) -> Path:
        """Return the repo-level config directory both natively and in Docker."""
        return get_project_root() / "config"

    @property
    def resolved_knowledge_dir(self) -> Path:
        """Return the repo-level knowledge directory both natively and in Docker."""
        return get_project_root() / "knowledge"

    @property
    def resolved_data_dir(self) -> Path:
        """Return the repo-level data directory both natively and in Docker."""
        return get_project_root() / "data"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


def get_settings() -> Settings:
    """Create a Settings instance from the current environment."""
    return Settings()
