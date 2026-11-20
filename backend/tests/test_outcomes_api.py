"""Comprehensive API route integration tests for Outcomes stage endpoints."""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.health import resolve_settings
from app.config import Settings, get_settings
from app.db import init_db
from app.ingest.parse import REQUIRED_COLUMNS
from app.llm.base import LLMResponse, LLMUsage
from app.main import create_app
from app.models import (
    Engagement,
    EvalRun,
    EvalRunStatus,
    Intervention,
    Kpi,
    OutcomeReview,
    PilotSimulation,
)


@pytest.fixture()
def outcomes_api_client(tmp_path: Path):
    db_path = tmp_path / "test_outcomes_api.db"
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path.as_posix()}",
        seed_on_start=False,
        llm_provider="fake",
        llm_api_key="test-key",
        llm_model="fake-model",
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[resolve_settings] = lambda: settings
    engine = app.state.engine
    init_db(engine)
    session_factory = app.state.session_factory

    with session_factory() as session:
        eng = Engagement(name="Kora Living", client_name="Kora Living", stage="build")
        session.add(eng)
        session.commit()
        eng_id = eng.id

    with TestClient(app) as client:
        yield client, settings, session_factory, eng_id


def _upload_dataset(client: TestClient, eng_id: int) -> int:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(REQUIRED_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for i in range(10):
        row = {col: "" for col in REQUIRED_COLUMNS}
        row["ticket_id"] = f"TICK-{i+1:03d}"
        row["customer_id"] = f"CUST-{i+1:03d}"
        row["created_at"] = "2026-01-01 10:00:00"
        row["assigned_at"] = "2026-01-01 11:00:00"
        row["first_response_at"] = "2026-01-01 12:00:00"
        row["resolved_at"] = "2026-01-01 15:00:00"
        row["category"] = "order_tracking"
        row["priority"] = "medium"
        row["queue"] = "Order support"
        row["status"] = "resolved"
        row["channel"] = "email"
        row["assigned_agent"] = "Agent-1"
        row["reassignment_count"] = "0"
        writer.writerow(row)
    files = {"file": ("test.csv", buf.getvalue().encode("utf-8"), "text/csv")}
    resp = client.post(f"/api/engagements/{eng_id}/datasets", files=files)
    assert resp.status_code == 201
    return resp.json()["id"]


def test_kpi_catalogue_endpoint(outcomes_api_client):
    client, _, _, eng_id = outcomes_api_client
    resp = client.get(f"/api/engagements/{eng_id}/outcomes/kpi-catalogue")
    assert resp.status_code == 200
    catalogue = resp.json()
    assert len(catalogue) >= 4
    metric_ids = [m["metric_id"] for m in catalogue]
    assert "first_response_time" in metric_ids
    assert "resolution_time" in metric_ids


def test_kpi_crud_lifecycle_and_baseline_recompute(outcomes_api_client):
    client, _, _, eng_id = outcomes_api_client
    _upload_dataset(client, eng_id)

    # 1. List initially empty
    resp = client.get(f"/api/engagements/{eng_id}/outcomes/kpis")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Create primary KPI
    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={
            "metric_id": "first_response_time",
            "name": "Primary FRT",
            "target_value": 1.0,
            "target_assumption": "Automation speeds up first response",
            "is_primary": True,
        },
    )
    assert resp.status_code == 201
    kpi_data = resp.json()
    kpi_id = kpi_data["id"]
    assert kpi_data["name"] == "Primary FRT"
    assert kpi_data["is_primary"] is True
    assert kpi_data["baseline"] is not None

    # 3. Patch KPI
    patch_resp = client.patch(
        f"/api/engagements/{eng_id}/outcomes/kpis/{kpi_id}",
        json={"target_value": 0.8, "name": "Updated FRT"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["name"] == "Updated FRT"
    assert patch_resp.json()["target_value"] == 0.8

    # 4. Recompute baseline
    recomp_resp = client.post(f"/api/engagements/{eng_id}/outcomes/kpis/{kpi_id}/recompute-baseline")
    assert recomp_resp.status_code == 200
    assert recomp_resp.json()["baseline"] is not None

    # 5. Delete KPI
    del_resp = client.delete(f"/api/engagements/{eng_id}/outcomes/kpis/{kpi_id}")
    assert del_resp.status_code == 204

    # Verify deleted
    resp = client.get(f"/api/engagements/{eng_id}/outcomes/kpis")
    assert resp.status_code == 200
    assert len(resp.json()) == 0


def test_intervention_crud_lifecycle(outcomes_api_client):
    client, _, _, eng_id = outcomes_api_client

    # 1. Get interventions triggers seeding of defaults
    resp = client.get(f"/api/engagements/{eng_id}/outcomes/interventions")
    assert resp.status_code == 200
    initial_items = resp.json()
    assert len(initial_items) == 4

    # 2. Create custom intervention
    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/interventions",
        json={
            "name": "Custom Escalation Workflow",
            "description": "Auto-escalate legal and churn risks",
            "impact": 5,
            "effort": 2,
            "risk": 1,
            "rationale": "High impact risk mitigation",
        },
    )
    assert resp.status_code == 201
    inter_data = resp.json()
    inter_id = inter_data["id"]
    assert inter_data["name"] == "Custom Escalation Workflow"
    assert inter_data["score"] == 0.5 * 5 + 0.3 * (6 - 2) + 0.2 * (6 - 1)

    # 3. Patch intervention status
    patch_resp = client.patch(
        f"/api/engagements/{eng_id}/outcomes/interventions/{inter_id}",
        json={"status": "selected", "impact": 4},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "selected"

    # 4. Delete custom intervention
    del_resp = client.delete(f"/api/engagements/{eng_id}/outcomes/interventions/{inter_id}")
    assert del_resp.status_code == 204


def test_simulation_crud_lifecycle(outcomes_api_client):
    client, _, session_factory, eng_id = outcomes_api_client
    _upload_dataset(client, eng_id)

    # 1. List simulations initially empty
    resp = client.get(f"/api/engagements/{eng_id}/outcomes/simulations")
    assert resp.status_code == 200
    assert resp.json() == []

    # 2. Run simulation
    sim_resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/simulations",
        json={
            "pilot_share": 0.5,
            "reduction_pct": 30.0,
            "adoption_pct": 80.0,
            "rework_share": 0.15,
            "seed": 42,
        },
    )
    assert sim_resp.status_code == 201
    sim_data = sim_resp.json()
    sim_id = sim_data["id"]
    assert "effect" in sim_data
    assert sim_data["simulated"] is True
    assert sim_data["parameters"]["seed"] == 42

    # 3. Get simulation by id
    get_resp = client.get(f"/api/engagements/{eng_id}/outcomes/simulations/{sim_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == sim_id

    # 4. Delete simulation
    del_resp = client.delete(f"/api/engagements/{eng_id}/outcomes/simulations/{sim_id}")
    assert del_resp.status_code == 204


def test_outcome_review_get_put_confirm_lifecycle(outcomes_api_client):
    client, _, session_factory, eng_id = outcomes_api_client

    # 1. Initially 404
    resp = client.get(f"/api/engagements/{eng_id}/outcomes/review")
    assert resp.status_code == 404

    # 2. Create review via PUT
    review_sections = {
        "what_improved": [
            {
                "claim": "Simulated handling time decreased by 12.5% under the pilot.",
                "basis": "simulated",
                "evidence_keys": ["simulation.difference"],
            }
        ],
        "what_did_not": [],
        "limitations": ["Assumed parameter distributions in synthetic evaluation."],
        "recommendation": {
            "value": "continue",
            "rationale": "Strong simulated efficiency gains observed across all queues.",
        },
        "next_steps": ["Expand shadow testing to email channel."],
    }
    put_resp = client.put(
        f"/api/engagements/{eng_id}/outcomes/review",
        json={"sections": review_sections},
    )
    assert put_resp.status_code == 200
    review_data = put_resp.json()
    assert review_data["sections"]["recommendation"]["value"] == "continue"
    assert review_data["confirmed_at"] is None

    # 3. Confirm review
    conf_resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/review/confirm",
        json={
            "final_recommendation": "continue",
            "acknowledged_simulated": True,
        },
    )
    assert conf_resp.status_code == 200
    assert conf_resp.json()["confirmed_at"] is not None
    assert conf_resp.json()["status"] == "confirmed"


def test_outcomes_api_error_paths_and_edge_cases(outcomes_api_client):
    client, _, session_factory, eng_id = outcomes_api_client
    _upload_dataset(client, eng_id)

    # 1. 404s for nonexistent resources
    assert client.patch(f"/api/engagements/{eng_id}/outcomes/kpis/9999", json={"name": "x"}).status_code == 404
    assert client.delete(f"/api/engagements/{eng_id}/outcomes/kpis/9999").status_code == 404
    assert client.post(f"/api/engagements/{eng_id}/outcomes/kpis/9999/recompute-baseline").status_code == 404
    assert client.patch(f"/api/engagements/{eng_id}/outcomes/interventions/9999", json={"impact": 3}).status_code == 404
    assert client.delete(f"/api/engagements/{eng_id}/outcomes/interventions/9999").status_code == 404
    assert client.get(f"/api/engagements/{eng_id}/outcomes/simulations/9999").status_code == 404
    assert client.delete(f"/api/engagements/{eng_id}/outcomes/simulations/9999").status_code == 404

    # 2. Deleting catalogue intervention returns 204
    resp = client.get(f"/api/engagements/{eng_id}/outcomes/interventions")
    cat_inter_id = resp.json()[0]["id"]
    assert client.delete(f"/api/engagements/{eng_id}/outcomes/interventions/{cat_inter_id}").status_code == 204
    # Subsequent delete of same returns 404
    assert client.delete(f"/api/engagements/{eng_id}/outcomes/interventions/{cat_inter_id}").status_code == 404

    # 3. Update remaining catalogue intervention score
    remaining_id = resp.json()[1]["id"]
    patch_inter = client.patch(
        f"/api/engagements/{eng_id}/outcomes/interventions/{remaining_id}",
        json={"impact": 5, "effort": 1, "risk": 1, "rationale": "High priority"},
    )
    assert patch_inter.status_code == 200
    assert patch_inter.json()["score"] == 5.0

    # 4. Create two KPIs and test primary demotion
    k1 = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={"metric_id": "first_response_time", "is_primary": True},
    ).json()["id"]
    k2 = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={"metric_id": "resolution_time", "is_primary": False},
    ).json()["id"]

    # Promote k2 to primary
    p_resp = client.patch(f"/api/engagements/{eng_id}/outcomes/kpis/{k2}", json={"is_primary": True})
    assert p_resp.status_code == 200
    assert p_resp.json()["is_primary"] is True

    # Verify k1 is now not primary
    kpis = {k["id"]: k for k in client.get(f"/api/engagements/{eng_id}/outcomes/kpis").json()}
    assert kpis[k1]["is_primary"] is False
    assert kpis[k2]["is_primary"] is True

    # 5. List simulations when simulation exists
    client.post(
        f"/api/engagements/{eng_id}/outcomes/simulations",
        json={"pilot_share": 0.5, "reduction_pct": 20.0, "adoption_pct": 80.0, "rework_share": 0.1},
    )
    sims = client.get(f"/api/engagements/{eng_id}/outcomes/simulations").json()
    assert len(sims) >= 1
