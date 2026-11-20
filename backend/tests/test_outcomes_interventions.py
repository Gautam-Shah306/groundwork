"""Tests for Outcomes interventions: scoring formula, seeding idempotency, and 1-5 validation."""

from __future__ import annotations

from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.api.health import resolve_settings
from app.config import Settings, get_settings
from app.db import init_db
from app.main import create_app
from app.models import Engagement, Intervention
from app.outcomes.service import calculate_intervention_score, seed_interventions_if_needed


@pytest.fixture()
def inter_client(tmp_path: Path):
    db_path = tmp_path / "test_inter.db"
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


def test_intervention_score_formula_and_sort_order(inter_client):
    """Test 21: Score formula = 0.5*impact + 0.3*(6-effort) + 0.2*(6-risk), sorted descending."""
    # Hand calculations:
    # 1. impact=5, effort=1, risk=1 -> 0.5*5 + 0.3*5 + 0.2*5 = 2.5 + 1.5 + 1.0 = 5.0
    # 2. impact=1, effort=5, risk=5 -> 0.5*1 + 0.3*1 + 0.2*1 = 0.5 + 0.3 + 0.2 = 1.0
    # 3. impact=4, effort=2, risk=3 -> 0.5*4 + 0.3*4 + 0.2*3 = 2.0 + 1.2 + 0.6 = 3.8
    assert calculate_intervention_score(5, 1, 1) == 5.0
    assert calculate_intervention_score(1, 5, 5) == 1.0
    assert calculate_intervention_score(4, 2, 3) == 3.8

    client, _, _, eng_id = inter_client
    # List interventions (triggers seeding of 4 catalogue interventions)
    resp = client.get(f"/api/engagements/{eng_id}/outcomes/interventions")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 4

    # Verify sorted strictly descending by score
    scores = [item["score"] for item in items]
    assert scores == sorted(scores, reverse=True)


def test_interventions_seeded_once_and_idempotent(inter_client):
    """Test 22: Seeded interventions are seeded once and idempotent on subsequent calls."""
    client, _, session_factory, eng_id = inter_client

    # First call: seeds 4 interventions
    r1 = client.get(f"/api/engagements/{eng_id}/outcomes/interventions")
    assert r1.status_code == 200
    items1 = r1.json()
    assert len(items1) == 4

    # Second call: returns same 4, does not duplicate
    r2 = client.get(f"/api/engagements/{eng_id}/outcomes/interventions")
    assert r2.status_code == 200
    items2 = r2.json()
    assert len(items2) == 4
    assert [i["id"] for i in items1] == [i["id"] for i in items2]

    # Verify seed_interventions_if_needed directly
    with session_factory() as session:
        seeded_again = seed_interventions_if_needed(session, eng_id)
        assert len(seeded_again) == 4


def test_intervention_validation_1_to_5(inter_client):
    """Test 23: Impact, effort, and risk outside 1..5 are rejected with 422."""
    client, _, _, eng_id = inter_client

    bad_payloads = [
        {"name": "Bad Impact Low", "impact": 0, "effort": 3, "risk": 3},
        {"name": "Bad Impact High", "impact": 6, "effort": 3, "risk": 3},
        {"name": "Bad Effort Low", "impact": 3, "effort": 0, "risk": 3},
        {"name": "Bad Effort High", "impact": 3, "effort": 6, "risk": 3},
        {"name": "Bad Risk Low", "impact": 3, "effort": 3, "risk": 0},
        {"name": "Bad Risk High", "impact": 3, "effort": 3, "risk": 6},
    ]
    for bad in bad_payloads:
        resp = client.post(f"/api/engagements/{eng_id}/outcomes/interventions", json=bad)
        assert resp.status_code == 422, f"Expected 422 for {bad}"

    # Valid payload 1..5 succeeds
    valid_resp = client.post(
        f"/api/engagements/{eng_id}/outcomes/interventions",
        json={"name": "Valid Human Intervention", "impact": 4, "effort": 2, "risk": 2, "rationale": "High value"},
    )
    assert valid_resp.status_code == 201
    assert valid_resp.json()["score"] == calculate_intervention_score(4, 2, 2)
