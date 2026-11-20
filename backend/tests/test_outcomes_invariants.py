"""Tests for Outcomes invariants (Tests 36-39).

Verifies cross-engagement isolation, audit log hygiene, absence of answer_key references,
and idempotent SQLite column migration.
"""

from pathlib import Path
import pytest
from sqlalchemy import text
from starlette.testclient import TestClient

from app.api.health import resolve_settings
from app.config import Settings, get_settings
from app.db import KPIS_COLUMNS, PILOT_SIMULATIONS_COLUMNS, ensure_columns, init_db
from app.main import create_app
from app.models import (
    AuditLog,
    Engagement,
    Intervention,
    Kpi,
    OutcomeReview,
    PilotSimulation,
)


@pytest.fixture()
def client_and_db(tmp_path: Path):
    db_path = tmp_path / "test_invariants.db"
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path.as_posix()}",
        seed_on_start=False,
        llm_provider="gemini",
        llm_api_key="test-key",
        llm_model="gemini-1.5-flash",
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[resolve_settings] = lambda: settings
    engine = app.state.engine
    init_db(engine)
    session_factory = app.state.session_factory

    with session_factory() as session:
        eng1 = Engagement(name="Client One", client_name="Client One", stage="build")
        eng2 = Engagement(name="Client Two", client_name="Client Two", stage="build")
        session.add_all([eng1, eng2])
        session.commit()
        eng1_id = eng1.id
        eng2_id = eng2.id

    with TestClient(app) as client:
        yield client, session_factory, eng1_id, eng2_id, engine


def test_cross_engagement_ids_return_404_and_engagement_delete_cascades(client_and_db):
    """Test 36: Cross-engagement access returns 404 and engagement deletion cascades."""
    client, session_factory, eng1_id, eng2_id, _ = client_and_db

    # Seed sample dataset for eng1
    client.post(f"/api/engagements/{eng1_id}/datasets/sample")

    # Create resources in eng1
    kpi_resp = client.post(
        f"/api/engagements/{eng1_id}/outcomes/kpis",
        json={"metric_id": "first_response_time", "target_value": 3.0, "target_assumption": "Routing with triage automation"},
    )
    assert kpi_resp.status_code == 201
    kpi_id = kpi_resp.json()["id"]

    int_resp = client.post(
        f"/api/engagements/{eng1_id}/outcomes/interventions",
        json={
            "name": "Auto triage",
            "description": "Auto triage routing",
            "impact": 4,
            "effort": 2,
            "risk": 2,
            "rationale": "High value automation",
            "status": "proposed",
        },
    )
    assert int_resp.status_code == 201
    int_id = int_resp.json()["id"]

    sim_resp = client.post(
        f"/api/engagements/{eng1_id}/outcomes/simulation",
        json={"pilot_share": 0.25, "reduction_pct": 0.3, "adoption_pct": 0.8, "rework_share": 0.15, "seed": 42},
    )
    assert sim_resp.status_code == 201
    sim_id = sim_resp.json()["id"]

    # Try accessing eng1 resources through eng2 -> must return 404
    assert client.delete(f"/api/engagements/{eng2_id}/outcomes/kpis/{kpi_id}").status_code == 404
    assert client.delete(f"/api/engagements/{eng2_id}/outcomes/interventions/{int_id}").status_code == 404
    assert client.get(f"/api/engagements/{eng2_id}/outcomes/simulations/{sim_id}").status_code == 404

    # Deleting eng1 cascades to KPIs, Interventions, Simulations
    del_resp = client.delete(f"/api/engagements/{eng1_id}")
    assert del_resp.status_code == 204

    with session_factory() as session:
        assert session.get(Kpi, kpi_id) is None
        assert session.get(Intervention, int_id) is None
        assert session.get(PilotSimulation, sim_id) is None


def test_audit_rows_contain_ids_and_parameters_only(client_and_db):
    """Test 37: Audit log rows contain only IDs and parameters, no ticket text or customer PII."""
    client, session_factory, eng1_id, _, _ = client_and_db

    # Seed sample dataset
    client.post(f"/api/engagements/{eng1_id}/datasets/sample")

    # Create KPI
    client.post(
        f"/api/engagements/{eng1_id}/outcomes/kpis",
        json={"metric_id": "first_response_time", "target_value": 3.0, "target_assumption": "Routing with triage automation"},
    )
    # Create Intervention
    client.post(
        f"/api/engagements/{eng1_id}/outcomes/interventions",
        json={
            "name": "Auto triage",
            "description": "Description",
            "impact": 4,
            "effort": 2,
            "risk": 2,
            "rationale": "High value automation",
            "status": "proposed",
        },
    )
    # Run simulation
    client.post(
        f"/api/engagements/{eng1_id}/outcomes/simulation",
        json={"pilot_share": 0.25, "reduction_pct": 0.3, "adoption_pct": 0.8, "rework_share": 0.15, "seed": 42},
    )

    with session_factory() as session:
        from sqlalchemy import select
        audit_entries = session.scalars(
            select(AuditLog).where(
                AuditLog.engagement_id == eng1_id,
                AuditLog.action.in_(["kpi_created", "intervention_created", "simulation_created"]),
            )
        ).all()
        assert len(audit_entries) >= 3
        for entry in audit_entries:
            details = entry.details
            assert isinstance(details, dict)
            # Ensure no large customer text or ticket payload in audit details
            for k, v in details.items():
                if isinstance(v, str):
                    assert "customer" not in v.lower()
                    assert len(v) < 200


def test_outcomes_code_never_references_answer_key_or_eval_ticket_text_or_label_names():
    """Test 38: Outcomes code never references answer_key.json, eval_tickets, or test set labels."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    outcomes_backend = repo_root / "backend" / "app" / "outcomes"
    outcomes_config = repo_root / "config" / "outcomes.yaml"

    forbidden_patterns = [
        "answer_key",
        "eval_tickets",
        "true_category",
        "true_priority",
        "ground_truth",
    ]

    files_to_check = list(outcomes_backend.glob("*.py"))
    if outcomes_config.exists():
        files_to_check.append(outcomes_config)

    for file_path in files_to_check:
        content = file_path.read_text(encoding="utf-8")
        for pattern in forbidden_patterns:
            assert pattern not in content, f"Forbidden pattern '{pattern}' found in {file_path}"


def test_ensure_columns_adds_outcome_columns_idempotently(tmp_path: Path):
    """Test 39: ensure_columns adds outcome columns idempotently on SQLite."""
    from sqlalchemy import create_engine
    db_file = tmp_path / "migration_test.db"
    engine = create_engine(f"sqlite:///{db_file.as_posix()}")

    # Create minimal tables without the newly added columns
    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE kpis (id INTEGER PRIMARY KEY, engagement_id INTEGER, name VARCHAR, target_value FLOAT, current_value FLOAT, unit VARCHAR)"
            )
        )
        conn.execute(
            text(
                "CREATE TABLE pilot_simulations (id INTEGER PRIMARY KEY, engagement_id INTEGER, parameters JSON, results JSON, created_at DATETIME)"
            )
        )

    # First call: should add missing columns
    ensure_columns(engine, "kpis", KPIS_COLUMNS)
    ensure_columns(engine, "pilot_simulations", PILOT_SIMULATIONS_COLUMNS)

    with engine.connect() as conn:
        kpi_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(kpis)")).fetchall()]
        assert "metric_id" in kpi_cols
        assert "direction" in kpi_cols
        assert "baseline_dataset_id" in kpi_cols

        sim_cols = [row[1] for row in conn.execute(text("PRAGMA table_info(pilot_simulations)")).fetchall()]
        assert "dataset_id" in sim_cols
        assert "eval_run_id" in sim_cols
        assert "seed" in sim_cols

    # Second call: must run without errors and remain identical
    ensure_columns(engine, "kpis", KPIS_COLUMNS)
    ensure_columns(engine, "pilot_simulations", PILOT_SIMULATIONS_COLUMNS)
