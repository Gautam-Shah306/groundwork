"""FastAPI application factory and ASGI entrypoint."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.activity import router as activity_router
from app.api.assistant import mark_stale_running_runs_failed, router as assistant_router
from app.api.brief import router as brief_router
from app.api.datasets import router as datasets_router
from app.api.diagnostics import router as diagnostics_router
from app.api.discovery import router as discovery_router
from app.api.engagements import router as engagements_router
from app.api.evaluation import router as evaluation_router
from app.api.health import router as health_router
from app.api.notes import router as notes_router
from app.api.outcomes import router as outcomes_router
from app.api.triage import router as triage_router
from app.config import Settings, get_settings
from app.db import create_db_engine, create_session_factory, init_db
from app.evaluation.runner import mark_interrupted_eval_runs_paused
from app.seed import seed_demo_data


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the Groundwork FastAPI application."""
    resolved_settings = settings if settings is not None else get_settings()
    engine = create_db_engine(resolved_settings.resolved_database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        init_db(engine)
        with session_factory() as session:
            mark_stale_running_runs_failed(session)
            mark_interrupted_eval_runs_paused(session)
            if resolved_settings.seed_on_start:
                seed_demo_data(session)
        yield
        for thread in getattr(_app.state, "assistant_threads", []):
            thread.join(timeout=2.0)
        for thread in getattr(_app.state, "eval_threads", []):
            thread.join(timeout=2.0)
        engine.dispose()

    application = FastAPI(
        title="Groundwork API",
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )
    if settings is not None:
        application.state.settings = settings
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.assistant_threads = []
    application.state.eval_threads = []

    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(health_router)
    application.include_router(engagements_router)
    application.include_router(notes_router)
    application.include_router(brief_router)
    application.include_router(activity_router)
    application.include_router(datasets_router)
    application.include_router(diagnostics_router)
    application.include_router(discovery_router)
    application.include_router(assistant_router)
    application.include_router(triage_router)
    application.include_router(evaluation_router)
    application.include_router(outcomes_router)
    return application


app = create_app()
