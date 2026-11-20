"""Tests for evaluation benchmark API endpoints (B5)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.health import resolve_settings
from app.config import Settings, get_project_root, get_settings
from app.db import create_db_engine, create_session_factory, init_db
from app.llm.base import LLMResponse
from app.llm.fake import FakeProvider
from app.main import create_app
from app.models import AuditLog, Engagement, EvalItem, EvalRun, EvalRunStatus


@pytest.fixture()
def eval_client(tmp_path: Path):
    db_path = tmp_path / "test_eval_api.db"
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path.as_posix()}",
        seed_on_start=False,
        llm_provider="fake",
        llm_api_key="test-secret-key",
        llm_model="fake-test-model",
        eval_pacing_seconds=0,
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


# 45. test_post_runs_202_and_starts_background_run
def test_post_runs_202_and_starts_background_run(eval_client) -> None:
    client, settings, session_factory, eng_id = eval_client

    with patch("app.api.evaluation._start_runner_thread") as mock_thread:
        resp = client.post(
            f"/api/engagements/{eng_id}/evaluation/runs",
            json={"sample_size": 20, "drafts_sample": 0},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "run_id" in data
        run_id = data["run_id"]
        mock_thread.assert_called_once()

    # Verify audit event
    with session_factory() as session:
        audit = session.scalar(
            select(AuditLog).where(
                AuditLog.engagement_id == eng_id,
                AuditLog.action == "eval_run_started",
            )
        )
        assert audit is not None
        assert audit.entity_id == str(run_id)


# A7.10 test_get_run_serves_cached_summary_without_calling_provider
def test_get_run_serves_cached_summary_without_calling_provider(eval_client) -> None:
    client, settings, session_factory, eng_id = eval_client
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="cached-model",
            sample_size=10,
            status=EvalRunStatus.completed,
            results={"summary": {"category_accuracy": 0.9}},
        )
        session.add(run)
        session.commit()
        run_id = run.id

    with patch("app.llm.factory.get_provider") as mock_gp:
        resp = client.get(f"/api/engagements/{eng_id}/evaluation/runs/{run_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"]["summary"]["category_accuracy"] == 0.9
        # Provider factory was NEVER called
        mock_gp.assert_not_called()


# 46. test_post_runs_409_when_run_already_in_progress
def test_post_runs_409_when_run_already_in_progress(eval_client) -> None:
    client, settings, session_factory, eng_id = eval_client
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=10,
            status=EvalRunStatus.running,
        )
        session.add(run)
        session.commit()

    resp = client.post(
        f"/api/engagements/{eng_id}/evaluation/runs",
        json={"sample_size": 10},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"]["code"] == "run_already_in_progress"


# 47. test_list_runs_returns_newest_first
def test_list_runs_returns_newest_first(eval_client) -> None:
    client, settings, session_factory, eng_id = eval_client
    with session_factory() as session:
        r1 = EvalRun(engagement_id=eng_id, model="m1", sample_size=5, status=EvalRunStatus.completed)
        r2 = EvalRun(engagement_id=eng_id, model="m2", sample_size=10, status=EvalRunStatus.running)
        session.add_all([r1, r2])
        session.commit()
        id1, id2 = r1.id, r2.id

    resp = client.get(f"/api/engagements/{eng_id}/evaluation/runs")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2
    ids = [d["id"] for d in data]
    assert ids.index(id2) < ids.index(id1)


# 48. test_get_run_returns_404_for_unknown_or_cross_engagement
def test_get_run_returns_404_for_unknown_or_cross_engagement(eval_client) -> None:
    client, settings, session_factory, eng_id = eval_client
    # Unknown run
    r404 = client.get(f"/api/engagements/{eng_id}/evaluation/runs/99999")
    assert r404.status_code == 404

    # Create run for another engagement
    with session_factory() as session:
        other_eng = Engagement(name="Other", client_name="Other", stage="build")
        session.add(other_eng)
        session.commit()
        other_run = EvalRun(engagement_id=other_eng.id, model="m", sample_size=5)
        session.add(other_run)
        session.commit()
        other_run_id = other_run.id

    # Cross engagement lookup
    r_cross = client.get(f"/api/engagements/{eng_id}/evaluation/runs/{other_run_id}")
    assert r_cross.status_code == 404


# 49. test_get_run_items_paginates_and_filters_failure_only
def test_get_run_items_paginates_and_filters_failure_only(eval_client) -> None:
    client, settings, session_factory, eng_id = eval_client
    with session_factory() as session:
        run = EvalRun(engagement_id=eng_id, model="m", sample_size=10, status=EvalRunStatus.completed)
        session.add(run)
        session.flush()
        # Item 1: correct
        it1 = EvalItem(run_id=run.id, ticket_id="EV-001", status="success", predicted_category="order_tracking", predicted_priority="medium")
        # Item 2: wrong priority (failure)
        it2 = EvalItem(run_id=run.id, ticket_id="EV-002", status="success", predicted_category="order_tracking", predicted_priority="low")
        # Item 3: error (failure)
        it3 = EvalItem(run_id=run.id, ticket_id="EV-003", status="error", error_code="timeout")
        session.add_all([it1, it2, it3])
        session.commit()
        run_id = run.id

    # Normal list
    r_all = client.get(f"/api/engagements/{eng_id}/evaluation/runs/{run_id}/items?page=1&page_size=2")
    assert r_all.status_code == 200
    data_all = r_all.json()
    assert data_all["total"] == 3
    assert len(data_all["items"]) == 2

    # failure_only filter
    r_fails = client.get(f"/api/engagements/{eng_id}/evaluation/runs/{run_id}/items?failure_only=true")
    assert r_fails.status_code == 200
    data_fails = r_fails.json()
    assert data_fails["total"] == 2
    fail_ids = {it["ticket_id"] for it in data_fails["items"]}
    assert fail_ids == {"EV-002", "EV-003"}


# 50. test_resume_run_200_and_restarts_background_run
def test_resume_run_200_and_restarts_background_run(eval_client) -> None:
    client, settings, session_factory, eng_id = eval_client
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=10,
            status=EvalRunStatus.paused,
            error={"code": "interrupted", "message": "Server restarted"},
        )
        session.add(run)
        session.commit()
        run_id = run.id

    with patch("app.api.evaluation._start_runner_thread") as mock_thread:
        resp = client.post(f"/api/engagements/{eng_id}/evaluation/runs/{run_id}/resume")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "running"
        assert data["error"] is None
        mock_thread.assert_called_once()


# 51. test_cancel_run_200_and_sets_status_cancelled
def test_cancel_run_200_and_sets_status_cancelled(eval_client) -> None:
    client, settings, session_factory, eng_id = eval_client
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=10,
            status=EvalRunStatus.running,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    resp = client.post(f"/api/engagements/{eng_id}/evaluation/runs/{run_id}/cancel")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "cancelled"

    # Verify audit event
    with session_factory() as session:
        audit = session.scalar(
            select(AuditLog).where(
                AuditLog.engagement_id == eng_id,
                AuditLog.action == "eval_run_cancelled",
            )
        )
        assert audit is not None


# 52. test_eval_code_never_modifies_eval_tickets_json
def test_eval_code_never_modifies_eval_tickets_json() -> None:
    fp_before = (get_project_root() / "data/eval_tickets.json").read_bytes()
    # Check that git status doesn't report eval_tickets.json changed
    import hashlib
    assert hashlib.sha256(fp_before).hexdigest() == "b3f97a247255ace5e1eaf3983dcea2e6c1f2432f9c538e4be0430f38b554c561"
