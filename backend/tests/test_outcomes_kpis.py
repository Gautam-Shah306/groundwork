"""Tests for Outcomes KPIs: baselines, targets, staleness, and catalogue endpoints."""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.health import resolve_settings
from app.config import Settings, get_settings
from app.db import init_db
from app.main import create_app
from app.models import Engagement


@pytest.fixture()
def outcomes_client(tmp_path: Path):
    db_path = tmp_path / "test_outcomes_kpis.db"
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


def test_kpi_requires_active_dataset(outcomes_client):
    """Test 8: Adding a KPI without an active dataset returns 422 actionable."""
    client, _, _, eng_id = outcomes_client
    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={"metric_id": "first_response_time"},
    )
    assert resp.status_code == 422
    assert "no active dataset" in resp.json()["detail"].lower()


def test_kpi_rejects_unknown_metric_id(outcomes_client):
    """Test 3: Reject unknown metric_id not in catalogue with 422."""
    client, _, _, eng_id = outcomes_client
    # Load sample dataset
    client.post(f"/api/engagements/{eng_id}/datasets/sample")

    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={"metric_id": "unknown_metric_id"},
    )
    assert resp.status_code == 422
    assert "catalogue" in resp.json()["detail"].lower()


def test_kpi_baseline_is_computed_and_matches_diagnostics_kpi(outcomes_client):
    """Test 2: Baselines are computed through metrics and match Diagnostics KPIs exactly."""
    client, _, _, eng_id = outcomes_client
    s_resp = client.post(f"/api/engagements/{eng_id}/datasets/sample")
    ds_id = s_resp.json()["id"]

    # Query diagnostics KPIs
    diag_resp = client.get(f"/api/engagements/{eng_id}/datasets/{ds_id}/diagnostics")
    assert diag_resp.status_code == 200
    diag_kpis = {k["metric_id"]: k["value"] for k in diag_resp.json()["kpis"]}

    # Create all 6 catalogue KPIs
    cat_resp = client.get(f"/api/engagements/{eng_id}/outcomes/kpi-catalogue")
    assert cat_resp.status_code == 200
    catalogue = cat_resp.json()
    assert len(catalogue) == 6

    for item in catalogue:
        m_id = item["metric_id"]
        create_resp = client.post(
            f"/api/engagements/{eng_id}/outcomes/kpis",
            json={"metric_id": m_id},
        )
        assert create_resp.status_code == 201
        data = create_resp.json()
        assert data["baseline"] is not None
        # Compare baseline value with Diagnostics KPI value
        assert data["baseline"]["value"] == diag_kpis[m_id]


def test_kpi_target_requires_assumption(outcomes_client):
    """Test 4: Setting a target requires target_assumption of at least 10 chars."""
    client, _, _, eng_id = outcomes_client
    client.post(f"/api/engagements/{eng_id}/datasets/sample")

    # Target without assumption -> 422
    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={"metric_id": "first_response_time", "target_value": 3.0},
    )
    assert resp.status_code == 422
    assert "at least 10 characters" in resp.json()["detail"]

    # Target with too short assumption -> 422
    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={"metric_id": "first_response_time", "target_value": 3.0, "target_assumption": "too short"},
    )
    assert resp.status_code == 422
    assert "at least 10 characters" in resp.json()["detail"]


def test_kpi_target_on_worsening_side_rejected(outcomes_client):
    """Test 5: Target on worsening side of baseline is rejected with 422."""
    client, _, _, eng_id = outcomes_client
    client.post(f"/api/engagements/{eng_id}/datasets/sample")

    # first_response_time baseline is ~5.07h. Target 10.0h is on worsening side
    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={
            "metric_id": "first_response_time",
            "target_value": 15.0,
            "target_assumption": "Assuming agents respond slower in the future",
        },
    )
    assert resp.status_code == 422
    assert "worsening side" in resp.json()["detail"].lower()


def test_exactly_one_primary_kpi(outcomes_client):
    """Test 6: Exactly one primary KPI per engagement (setting new primary clears old)."""
    client, _, _, eng_id = outcomes_client
    client.post(f"/api/engagements/{eng_id}/datasets/sample")

    r1 = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={"metric_id": "first_response_time", "is_primary": True},
    )
    k1_id = r1.json()["id"]
    assert r1.json()["is_primary"] is True

    r2 = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={"metric_id": "triage_time", "is_primary": True},
    )
    k2_id = r2.json()["id"]
    assert r2.json()["is_primary"] is True

    # List KPIs: k1 should be False, k2 should be True
    kpis = client.get(f"/api/engagements/{eng_id}/outcomes/kpis").json()
    k1 = next(k for k in kpis if k["id"] == k1_id)
    k2 = next(k for k in kpis if k["id"] == k2_id)
    assert k1["is_primary"] is False
    assert k2["is_primary"] is True


def test_stale_baseline_flagged_when_active_dataset_changes_and_recompute_fixes_it(outcomes_client):
    """Test 7: Stale baseline is flagged when active dataset changes, and recompute updates it."""
    client, _, _, eng_id = outcomes_client
    s1 = client.post(f"/api/engagements/{eng_id}/datasets/sample").json()
    ds1_id = s1["id"]

    k_resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={"metric_id": "first_response_time"},
    ).json()
    k_id = k_resp["id"]
    assert k_resp["is_stale"] is False

    # Upload a second sample dataset to change active dataset
    s2 = client.post(f"/api/engagements/{eng_id}/datasets/sample").json()
    ds2_id = s2["id"]
    assert ds2_id != ds1_id

    # List KPIs: kpi should now be marked stale
    kpis = client.get(f"/api/engagements/{eng_id}/outcomes/kpis").json()
    k = next(item for item in kpis if item["id"] == k_id)
    assert k["is_stale"] is True

    # Recompute baseline
    re_resp = client.post(f"/api/engagements/{eng_id}/outcomes/kpis/{k_id}/recompute-baseline")
    assert re_resp.status_code == 200
    assert re_resp.json()["is_stale"] is False
    assert re_resp.json()["baseline"]["dataset_id"] == ds2_id


def test_planned_change_is_labelled_and_no_improvement_percentage_is_returned(outcomes_client):
    """Test 9: Planned change (target minus baseline) is returned with exact label and no %."""
    client, _, _, eng_id = outcomes_client
    client.post(f"/api/engagements/{eng_id}/datasets/sample")

    resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/kpis",
        json={
            "metric_id": "first_response_time",
            "target_value": 3.0,
            "target_assumption": "Target based on implementing dedicated triage routing",
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    pc = data["planned_change"]
    assert pc is not None
    assert pc["label"] == "Planned change, not an outcome"
    assert isinstance(pc["value"], (int, float))
    assert "percent" not in pc
    assert "improvement_pct" not in pc
