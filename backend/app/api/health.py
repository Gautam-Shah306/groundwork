"""Health check API endpoint."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from app.config import Settings, get_settings

router = APIRouter(prefix="/api", tags=["health"])


class HealthResponse(BaseModel):
    """Public health payload that never exposes secrets or full connection paths."""

    status: str
    version: str
    llm_configured: bool
    database_url_scheme: str


def resolve_settings(request: Request) -> Settings:
    """Resolve settings from app state when injected, or load from environment."""
    configured = getattr(request.app.state, "settings", None)
    if isinstance(configured, Settings):
        return configured
    return get_settings()


@router.get("/health", response_model=HealthResponse)
def get_health(settings: Settings = Depends(resolve_settings)) -> HealthResponse:
    """Return service health without exposing API keys or full database URLs."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
        llm_configured=settings.llm_configured,
        database_url_scheme=settings.database_url_scheme,
    )
