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


TRIAGE_PROPOSALS_COLUMNS: dict[str, str] = {
    "subject": "VARCHAR(200)",
    "channel": "VARCHAR(60)",
    "ticket_hash": "VARCHAR(64)",
    "secondary_category": "VARCHAR(120)",
    "signals": "JSON",
    "flags": "JSON",
    "tool_trace": "JSON",
    "rationale": "TEXT",
    "escalation": "BOOLEAN DEFAULT 0",
    "policy_refs": "JSON",
    "reviewer_note": "TEXT",
    "model": "VARCHAR(120)",
    "usage": "JSON",
    "error": "JSON",
    "decided_by": "VARCHAR(120)",
    "decision_reason": "VARCHAR(300)",
    "edited": "BOOLEAN DEFAULT 0",
}

EVAL_RUNS_COLUMNS: dict[str, str] = {
    "status": "VARCHAR(30) DEFAULT 'running'",
    "config": "JSON",
    "progress_done": "INTEGER DEFAULT 0",
    "progress_total": "INTEGER DEFAULT 0",
    "error": "JSON",
    "usage": "JSON",
    "config_fingerprint": "VARCHAR(64) DEFAULT ''",
    "started_at": "DATETIME",
    "finished_at": "DATETIME",
}

KPIS_COLUMNS: dict[str, str] = {
    "metric_id": "VARCHAR(64) DEFAULT ''",
    "direction": "VARCHAR(32) DEFAULT 'lower_is_better'",
    "baseline_dataset_id": "INTEGER",
    "target_value": "FLOAT",
    "status": "VARCHAR(32) DEFAULT 'active'",
}

PILOT_SIMULATIONS_COLUMNS: dict[str, str] = {
    "dataset_id": "INTEGER",
    "eval_run_id": "INTEGER",
    "seed": "INTEGER DEFAULT 42",
    "results_hash": "VARCHAR(64) DEFAULT ''",
}


def ensure_columns(engine: Engine, table: str, columns: dict[str, str]) -> None:
    """Add columns to an existing table if they are missing (column-exists guard)."""
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            result = conn.exec_driver_sql(f"PRAGMA table_info({table})")
            existing = [row[1] for row in result.fetchall()]
            if existing:
                for col_name, sql_type in columns.items():
                    if col_name not in existing:
                        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {col_name} {sql_type}")
                conn.commit()


def ensure_agent_runs_usage_column(engine: Engine) -> None:
    """Add the usage column to agent_runs if the table exists but the column is missing."""
    ensure_columns(engine, "agent_runs", {"usage": "JSON"})


def init_db(engine: Engine) -> None:
    """Create all declared database tables if they do not yet exist."""
    Base.metadata.create_all(bind=engine)
    ensure_columns(engine, "agent_runs", {"usage": "JSON"})
    ensure_columns(engine, "triage_proposals", TRIAGE_PROPOSALS_COLUMNS)
    ensure_columns(engine, "eval_runs", EVAL_RUNS_COLUMNS)
    ensure_columns(engine, "kpis", KPIS_COLUMNS)
    ensure_columns(engine, "pilot_simulations", PILOT_SIMULATIONS_COLUMNS)
    with engine.connect() as conn:
        if engine.dialect.name == "sqlite":
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_triage_proposals_eng_ticket_hash "
                "ON triage_proposals (engagement_id, ticket_hash)"
            )
            conn.exec_driver_sql(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_eval_items_run_ticket "
                "ON eval_items (run_id, ticket_id)"
            )
            conn.commit()


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
