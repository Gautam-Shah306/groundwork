"""Tests for evaluation benchmark runner (B5)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import create_db_engine, create_session_factory, init_db
from app.evaluation.runner import EvaluationRunner, mark_interrupted_eval_runs_paused
from app.llm.base import LLMMessage, LLMProvider, LLMResponse
from app.llm.errors import LLMAuthError, LLMQuotaExhausted, LLMRateLimited
from app.llm.fake import FakeProvider
from app.models import Engagement, EvalItem, EvalRun, EvalRunStatus


def _mock_classification_response(category: str = "order_tracking", signals: list[str] | None = None) -> LLMResponse:
    return LLMResponse(
        text=json.dumps({
            "category": category,
            "secondary_category": None,
            "signals": [{"signal": s, "source_quote": "test quote"} for s in (signals or [])],
            "rationale": "Test classification",
        }),
        tool_calls=[],
    )


@pytest.fixture()
def eval_db(tmp_path: Path):
    db_path = tmp_path / "test_eval_runner.db"
    settings = Settings(
        _env_file=None,
        database_url=f"sqlite:///{db_path.as_posix()}",
        seed_on_start=False,
        eval_pacing_seconds=0,
        eval_max_rate_limit_waits=2,
        eval_max_wait_seconds=5,
    )
    engine = create_db_engine(settings.resolved_database_url)
    init_db(engine)
    session_factory = create_session_factory(engine)

    with session_factory() as session:
        eng = Engagement(name="Kora Living", client_name="Kora Living", stage="build")
        session.add(eng)
        session.commit()
        eng_id = eng.id

    return session_factory, eng_id, settings


# 37. test_runner_executes_sample_and_updates_progress
def test_runner_executes_sample_and_updates_progress(eval_db) -> None:
    session_factory, eng_id, settings = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=3,
            status=EvalRunStatus.running,
            config={"sample_size": 3, "drafts_sample": 0},
            progress_done=0,
            progress_total=3,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    fake_provider = FakeProvider([_mock_classification_response() for _ in range(5)])
    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=fake_provider,
        sleep_fn=lambda _: None,
    )
    runner.run()

    with session_factory() as session:
        completed_run = session.get(EvalRun, run_id)
        assert completed_run.status == EvalRunStatus.completed
        assert completed_run.progress_done == 3
        assert completed_run.progress_total == 3
        assert completed_run.results is not None
        assert "summary" in completed_run.results
        items = session.scalars(select(EvalItem).where(EvalItem.run_id == run_id)).all()
        assert len(items) == 3


# 38. test_runner_pauses_on_quota_error_without_crashing
def test_runner_pauses_on_quota_error_without_crashing(eval_db) -> None:
    session_factory, eng_id, settings = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=3,
            status=EvalRunStatus.running,
            config={"sample_size": 3},
            progress_done=0,
            progress_total=3,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    class QuotaProvider(LLMProvider):
        model_name = "test"
        def generate(self, *args, **kwargs):
            raise LLMQuotaExhausted("Credits exhausted")

    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=QuotaProvider(),
        sleep_fn=lambda _: None,
    )
    runner.run()

    with session_factory() as session:
        paused_run = session.get(EvalRun, run_id)
        assert paused_run.status == EvalRunStatus.paused
        assert paused_run.error is not None
        assert paused_run.error["code"] == "llm_quota_exhausted"


# 39. test_runner_pauses_on_auth_error
def test_runner_pauses_on_auth_error(eval_db) -> None:
    session_factory, eng_id, settings = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=3,
            status=EvalRunStatus.running,
            config={"sample_size": 3},
            progress_done=0,
            progress_total=3,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    class AuthProvider(LLMProvider):
        model_name = "test"
        def generate(self, *args, **kwargs):
            raise LLMAuthError("Invalid key")

    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=AuthProvider(),
        sleep_fn=lambda _: None,
    )
    runner.run()

    with session_factory() as session:
        paused_run = session.get(EvalRun, run_id)
        assert paused_run.status == EvalRunStatus.paused
        assert paused_run.error["code"] == "llm_auth_error"


# 40. test_runner_retries_on_rate_limit_up_to_max_waits
def test_runner_retries_on_rate_limit_up_to_max_waits(eval_db) -> None:
    session_factory, eng_id, settings = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=1,
            status=EvalRunStatus.running,
            config={"sample_size": 1},
            progress_done=0,
            progress_total=1,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    call_count = 0

    class RateLimitThenSucceedProvider(LLMProvider):
        model_name = "test"
        def generate(self, *args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise LLMRateLimited("Rate limited", retry_after_seconds=0.1)
            return _mock_classification_response()

    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=RateLimitThenSucceedProvider(),
        sleep_fn=lambda _: None,
    )
    runner.run()

    assert call_count == 3
    with session_factory() as session:
        r = session.get(EvalRun, run_id)
        assert r.status == EvalRunStatus.completed


# 41. test_runner_stops_cleanly_on_cancel
def test_runner_stops_cleanly_on_cancel(eval_db) -> None:
    session_factory, eng_id, settings = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=10,
            status=EvalRunStatus.running,
            config={"sample_size": 10},
            progress_done=0,
            progress_total=10,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    fake_provider = FakeProvider([_mock_classification_response() for _ in range(10)])
    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=fake_provider,
        sleep_fn=lambda _: None,
    )
    runner.stop_event.set()
    runner.run()

    with session_factory() as session:
        r = session.get(EvalRun, run_id)
        assert r.status == EvalRunStatus.cancelled


# 42. test_runner_resumes_only_incomplete_tickets
def test_runner_resumes_only_incomplete_tickets(eval_db) -> None:
    from app.evaluation.dataset import load_eval_tickets, select_sample
    session_factory, eng_id, settings = eval_db
    tickets = select_sample(load_eval_tickets(), 3)
    completed_tid = tickets[0].id

    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=3,
            status=EvalRunStatus.paused,
            config={"sample_size": 3},
            progress_done=1,
            progress_total=3,
        )
        session.add(run)
        session.flush()
        # Add 1 successful item from the sample
        session.add(EvalItem(run_id=run.id, ticket_id=completed_tid, status="success", predicted_category="order_tracking"))
        session.commit()
        run_id = run.id

    # Provider should only be called for the 2 remaining tickets
    fake_provider = FakeProvider([_mock_classification_response() for _ in range(5)])
    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=fake_provider,
        sleep_fn=lambda _: None,
    )
    runner.run()

    assert len(fake_provider.calls) == 2
    with session_factory() as session:
        r = session.get(EvalRun, run_id)
        assert r.status == EvalRunStatus.completed
        assert r.progress_done == 3


# 43. test_runner_optional_draft_check_runs_only_first_k_drafts
def test_runner_optional_draft_check_runs_only_first_k_drafts(eval_db) -> None:
    session_factory, eng_id, settings = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=3,
            status=EvalRunStatus.running,
            config={"sample_size": 3, "drafts_sample": 1},
            progress_done=0,
            progress_total=3,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    draft_response = LLMResponse(
        text=json.dumps({
            "reply_text": "Thank you for contacting us.",
            "policy_refs": ["1. Returns and cancellations"],
            "reviewer_note": "Ready for approval",
        }),
        tool_calls=[],
    )
    # Responses: ticket 1 classify, ticket 1 draft, ticket 2 classify, ticket 3 classify
    fake_provider = FakeProvider([
        _mock_classification_response(),
        draft_response,
        _mock_classification_response(),
        _mock_classification_response(),
    ])
    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=fake_provider,
        sleep_fn=lambda _: None,
    )
    runner.run()

    with session_factory() as session:
        items = session.scalars(select(EvalItem).where(EvalItem.run_id == run_id).order_by(EvalItem.id.asc())).all()
        assert len(items) == 3
        assert items[0].draft is not None
        assert items[0].draft["reply"] == "Thank you for contacting us."
        assert items[1].draft is None
        assert items[2].draft is None


# 44. test_startup_hook_marks_running_eval_runs_paused
def test_startup_hook_marks_running_eval_runs_paused(eval_db) -> None:
    session_factory, eng_id, _ = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=5,
            status=EvalRunStatus.running,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    with session_factory() as session:
        count = mark_interrupted_eval_runs_paused(session)
        assert count == 1
        r = session.get(EvalRun, run_id)
        assert r.status == EvalRunStatus.paused
        assert r.error["code"] == "interrupted"
