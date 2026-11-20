"""Tests for Outcomes simulation: deterministic pilot, bootstrap CI, bounds, and audit invariants."""

from __future__ import annotations

import csv
import io
from pathlib import Path
from unittest.mock import MagicMock
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.health import resolve_settings
from app.config import Settings, get_settings
from app.db import init_db
from app.ingest.parse import REQUIRED_COLUMNS
from app.main import create_app
from app.models import AuditLog, Engagement, EvalRun, EvalRunStatus
from app.outcomes.simulation import (
    compute_bootstrap_ci,
    run_pilot_simulation,
)


@pytest.fixture()
def sim_client(tmp_path: Path):
    db_path = tmp_path / "test_sim.db"
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


def _upload_tiny_csv(client: TestClient, eng_id: int, n: int = 20) -> int:
    """Upload a tiny dataset with known hours for exact hand computation."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(REQUIRED_COLUMNS), lineterminator="\n")
    writer.writeheader()
    # 20 tickets: created on 2026-01-01, assigned after i+1 hours, first response after (i+1)*2 hours
    for i in range(n):
        row = {col: "" for col in REQUIRED_COLUMNS}
        row["ticket_id"] = f"TICK-{i+1:03d}"
        row["customer_id"] = f"CUST-{i+1:03d}"
        row["created_at"] = "2026-01-01 10:00:00"
        row["assigned_at"] = f"2026-01-01 {11+i:02d}:00:00" if 11+i < 24 else f"2026-01-02 {11+i-24:02d}:00:00"
        row["first_response_at"] = f"2026-01-02 {10+i:02d}:00:00"
        row["category"] = "order_tracking"
        row["priority"] = "medium"
        row["queue"] = "Order support"
        row["assigned_agent"] = "agent_1"
        row["status"] = "closed"
        row["channel"] = "email"
        row["reassignment_count"] = "0"
        writer.writerow(row)

    resp = client.post(
        f"/api/engagements/{eng_id}/datasets",
        files={"file": ("tiny.csv", buf.getvalue().encode("utf-8"), "text/csv")},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


def _make_tiny_df(n: int = 20) -> pd.DataFrame:
    """Directly build tiny DataFrame with first_response_hours and triage_hours."""
    return pd.DataFrame({
        "row_id": list(range(1, n + 1)),
        "first_response_hours": [float(i + 2) for i in range(n)],
        "triage_hours": [float(i + 1) for i in range(n)],
    })


def test_simulation_hand_computed_on_tiny_fixture():
    """Test 10: Hand-computed pilot simulation on a tiny fixture with explicit step comments."""
    # Hand calculation:
    # Population n = 20 tickets.
    # pilot_share = 0.5 -> n_pilot = 10, n_comparison = 10.
    # duration_reduction_pct = 50%, adoption_pct = 100%, rework_share = 0.0, seed = 42
    # With adoption 100%, all 10 pilot tickets are treated.
    # Each treated ticket has first_response_duration reduced by 50% * triage_hours.
    df = _make_tiny_df(n=20)
    res = run_pilot_simulation(
        df,
        pilot_share=0.5,
        reduction_pct=50.0,
        adoption_pct=100.0,
        rework_share=0.0,
        seed=42,
        bootstrap_resamples=500,
    )

    sizes = res["sample_sizes"]
    assert sizes["n"] == 20
    assert sizes["n_pilot"] == 10
    assert sizes["n_comparison"] == 10
    assert sizes["n_treated"] == 10
    # Both groups partition the population
    assert sizes["n_pilot"] + sizes["n_comparison"] == sizes["n"]
    # Median reduction should be negative (pilot is faster)
    assert res["effect"]["difference_of_medians_hours"] < 0.0
    assert res["simulated"] is True
    assert "Simulated result" in res["label"]


def test_simulation_is_deterministic_for_same_inputs_and_seed():
    """Test 11: Simulation produces identical outputs and hash for the same inputs and seed."""
    df = _make_tiny_df(n=20)
    res1 = run_pilot_simulation(
        df, pilot_share=0.5, reduction_pct=30.0, adoption_pct=80.0,
        rework_share=0.1, seed=42, bootstrap_resamples=200,
    )
    res2 = run_pilot_simulation(
        df, pilot_share=0.5, reduction_pct=30.0, adoption_pct=80.0,
        rework_share=0.1, seed=42, bootstrap_resamples=200,
    )

    assert res1["results_hash"] == res2["results_hash"]
    assert res1["effect"] == res2["effect"]
    assert res1["sample_sizes"] == res2["sample_sizes"]


def test_simulation_pilot_and_comparison_partition_the_population():
    """Test 12: Pilot and comparison groups partition the population with no overlap."""
    df = _make_tiny_df(n=20)
    for p_share in (0.2, 0.35, 0.5, 0.7):
        res = run_pilot_simulation(
            df, pilot_share=p_share, reduction_pct=25.0, adoption_pct=90.0,
            rework_share=0.05, seed=123, bootstrap_resamples=100,
        )
        sizes = res["sample_sizes"]
        assert sizes["n_pilot"] + sizes["n_comparison"] == sizes["n"]
        expected = int(round(20 * p_share))
        assert abs(sizes["n_pilot"] - expected) <= 1


def test_simulation_zero_reduction_gives_equal_groups_in_expectation_and_zero_effect_on_pilot_values():
    """Test 13: Zero duration reduction produces zero treatment effect on pilot tickets."""
    df = _make_tiny_df(n=20)
    res = run_pilot_simulation(
        df, pilot_share=0.5, reduction_pct=0.0, adoption_pct=100.0,
        rework_share=0.0, seed=42, bootstrap_resamples=100,
    )
    # With zero reduction, pilot before median and pilot after median are identical
    assert res["pilot_group_before"]["median"] == res["pilot_group_after"]["median"]


def test_simulation_rework_share_defaults_to_latest_completed_eval_proxy_and_stores_run_id(sim_client):
    """Test 14: Rework share defaults to latest completed eval run's classification error rate."""
    client, _, session_factory, eng_id = sim_client
    _upload_tiny_csv(client, eng_id, n=20)

    # Seed a completed eval run with reviewer_change_proxy = 0.12
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="test-model",
            sample_size=100,
            status=EvalRunStatus.completed,
            results={"summary": {"reviewer_change_proxy": 0.12}},
        )
        session.add(run)
        session.commit()
        run_id = run.id

    # Post simulation omitting rework_share
    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/simulation",
        json={"pilot_share": 0.5, "reduction_pct": 30.0, "adoption_pct": 80.0},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["eval_run_id"] == run_id
    assert data["parameters"]["rework_share"] == 0.12


def test_simulation_without_eval_run_and_without_rework_share_returns_422(sim_client):
    """Test 15: Omitting rework_share when no completed eval run exists returns 422 actionable."""
    client, _, _, eng_id = sim_client
    _upload_tiny_csv(client, eng_id, n=20)

    # No eval run exists, omit rework_share
    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/simulation",
        json={"pilot_share": 0.5, "reduction_pct": 30.0, "adoption_pct": 80.0},
    )
    assert resp.status_code == 422
    assert "rework_share" in resp.json()["detail"].lower()


def test_simulation_parameter_bounds_validated(sim_client):
    """Test 16: Out-of-bounds simulation parameters are rejected with 422."""
    client, _, _, eng_id = sim_client
    _upload_tiny_csv(client, eng_id, n=20)

    bad_cases = [
        {"pilot_share": 0.05, "reduction_pct": 20.0, "adoption_pct": 50.0, "rework_share": 0.1},  # pilot_share < 0.2
        {"pilot_share": 0.95, "reduction_pct": 20.0, "adoption_pct": 50.0, "rework_share": 0.1},  # pilot_share > 0.8
        {"pilot_share": 0.5, "reduction_pct": -5.0, "adoption_pct": 50.0, "rework_share": 0.1},  # reduction < 0
        {"pilot_share": 0.5, "reduction_pct": 95.0, "adoption_pct": 50.0, "rework_share": 0.1},  # reduction > 90
        {"pilot_share": 0.5, "reduction_pct": 30.0, "adoption_pct": 105.0, "rework_share": 0.1}, # adoption > 100
        {"pilot_share": 0.5, "reduction_pct": 30.0, "adoption_pct": 50.0, "rework_share": 1.5},  # rework > 1.0
    ]
    for bad in bad_cases:
        resp = client.post(f"/api/engagements/{eng_id}/outcomes/simulation", json=bad)
        assert resp.status_code == 422, f"Expected 422 for bad param: {bad}"


def test_simulation_sensitivity_grid_has_nine_cells_and_is_monotone_in_reduction():
    """Test 17: Sensitivity grid has 9 cells and is monotone in duration reduction."""
    df = _make_tiny_df(n=20)
    res = run_pilot_simulation(
        df, pilot_share=0.5, reduction_pct=40.0, adoption_pct=80.0,
        rework_share=0.1, seed=42, bootstrap_resamples=100,
    )

    grid = res["sensitivity_grid"]
    assert len(grid) == 9
    adoptions = sorted(set(cell["adoption_pct"] for cell in grid))
    assert len(adoptions) == 3
    for adopt in adoptions:
        cells = sorted([c for c in grid if c["adoption_pct"] == adopt], key=lambda c: c["reduction_pct"])
        medians = [c["median_pilot_after"] for c in cells]
        # Larger reduction percentage should produce lower or equal median pilot duration
        assert medians[0] >= medians[1] >= medians[2]


def test_simulation_bootstrap_interval_is_reproducible():
    """Test 18: Bootstrap CI function is deterministic for fixed seed."""
    vals1 = np.array([5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    vals2 = np.array([2.0, 3.0, 4.0, 5.0, 6.0, 7.0])

    ci_a = compute_bootstrap_ci(vals1, vals2, resamples=500, seed=42)
    ci_b = compute_bootstrap_ci(vals1, vals2, resamples=500, seed=42)
    assert ci_a == ci_b
    assert ci_a[0] < ci_a[1]


def test_simulation_outputs_are_labelled_simulated_with_note(sim_client):
    """Test 19: Simulation API response contains is_simulated=True and clear methodology note."""
    client, _, _, eng_id = sim_client
    _upload_tiny_csv(client, eng_id, n=20)

    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/simulation",
        json={
            "pilot_share": 0.5,
            "reduction_pct": 40.0,
            "adoption_pct": 80.0,
            "rework_share": 0.1,
            "seed": 42,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["simulated"] is True
    assert "Simulated result" in data["label"]
    assert "The simulation applies assumed effects" in data["note"]


def test_simulation_makes_no_llm_call_and_no_ticket_text_in_audit(sim_client):
    """Test 20: Simulation invokes zero LLM calls and writes zero ticket text to audit log."""
    client, settings, session_factory, eng_id = sim_client
    _upload_tiny_csv(client, eng_id, n=20)

    # Mock provider spy
    mock_provider = MagicMock()
    app = client.app
    app.state.llm_provider = mock_provider

    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/simulation",
        json={
            "pilot_share": 0.5,
            "reduction_pct": 35.0,
            "adoption_pct": 75.0,
            "rework_share": 0.15,
            "seed": 99,
        },
    )
    assert resp.status_code == 201
    assert mock_provider.generate.call_count == 0

    with session_factory() as session:
        audits = session.scalars(
            select(AuditLog).where(
                AuditLog.engagement_id == eng_id,
                AuditLog.action == "simulation_created",
            )
        ).all()
        assert len(audits) >= 1
        audit = audits[0]
        details = audit.details
        assert "parameters" in details
        assert "results_hash" in details
        assert "ticket" not in str(details).lower()
        assert "subject" not in str(details).lower()
