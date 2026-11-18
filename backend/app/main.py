"""FastAPI application factory and ASGI entrypoint."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the Groundwork FastAPI application."""
    resolved_settings = settings if settings is not None else get_settings()

    application = FastAPI(
        title="Groundwork API",
        version=resolved_settings.app_version,
    )
    if settings is not None:
        application.state.settings = settings

    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    return application


app = create_app()
