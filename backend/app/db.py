"""Database engine, session factory, and FastAPI dependency."""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.models import Base


def create_db_engine(database_url: str) -> Engine:
    """Create a SQLAlchemy engine with SQLite foreign-key enforcement."""
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args, future=True)

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.close()

    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Create a configured sessionmaker bound to the provided engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def ensure_agent_runs_usage_column(engine: Engine) -> None:
    """Add the usage column to agent_runs if the table exists but the column is missing."""
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            result = conn.exec_driver_sql("PRAGMA table_info(agent_runs)")
            columns = [row[1] for row in result.fetchall()]
            if columns and "usage" not in columns:
                conn.exec_driver_sql("ALTER TABLE agent_runs ADD COLUMN usage JSON")
                conn.commit()


def init_db(engine: Engine) -> None:
    """Create all declared database tables if they do not yet exist."""
    Base.metadata.create_all(bind=engine)
    ensure_agent_runs_usage_column(engine)


def get_db(request: Request) -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session from application state."""
    session_factory: sessionmaker[Session] | None = getattr(
        request.app.state, "session_factory", None
    )
    if session_factory is None:
        settings: Settings = getattr(request.app.state, "settings", None) or get_settings()
        engine = create_db_engine(settings.resolved_database_url)
        init_db(engine)
        session_factory = create_session_factory(engine)
        request.app.state.engine = engine
        request.app.state.session_factory = session_factory

    db = session_factory()
    try:
        yield db
    finally:
        db.close()
