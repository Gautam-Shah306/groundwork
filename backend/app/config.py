"""Application configuration loaded from environment variables."""

from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


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
    llm_model: str = "gemini-2.5-flash"
    database_url: str = "sqlite:///./data/groundwork.db"
    cors_origins: str = "http://localhost:5173"

    @property
    def llm_configured(self) -> bool:
        """Return whether a non-empty LLM API key is configured."""
        return bool(self.llm_api_key.strip())

    @property
    def database_url_scheme(self) -> str:
        """Return only the URL scheme for the database connection string."""
        parsed = urlparse(self.database_url)
        return parsed.scheme or "unknown"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a clean list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


def get_settings() -> Settings:
    """Create a Settings instance from the current environment."""
    return Settings()
