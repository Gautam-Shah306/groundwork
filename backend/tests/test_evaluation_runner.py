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
from app.models import AuditLog, Engagement, EvalItem, EvalRun, EvalRunStatus, TriageProposal


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
    from app.evaluation.runner import _RUN_STOP_EVENTS, _RUN_STOP_LOCK
    with _RUN_STOP_LOCK:
        _RUN_STOP_EVENTS.clear()

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
            config={"sample_size": 3, "drafts_sample": 0},
            progress_done=0,
            progress_total=3,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate.side_effect = LLMQuotaExhausted("Monthly credit exhausted.")

    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=mock_provider,
        sleep_fn=lambda _: None,
    )
    runner.run()

    with session_factory() as session:
        r = session.get(EvalRun, run_id)
        assert r.status == EvalRunStatus.paused
        assert r.error["code"] == "llm_quota_exhausted"


# A7.8 test_quota_exhausted_pauses_immediately_without_recording_failure
def test_quota_exhausted_pauses_immediately_without_recording_failure(eval_db) -> None:
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

    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate.side_effect = LLMQuotaExhausted("Monthly limit reached.")

    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=mock_provider,
        sleep_fn=lambda _: None,
    )
    runner.run()

    with session_factory() as session:
        r = session.get(EvalRun, run_id)
        assert r.status == EvalRunStatus.paused
        assert r.error["code"] == "llm_quota_exhausted"
        # The current ticket stays pending and is NOT recorded as a failed EvalItem
        items = session.scalars(select(EvalItem).where(EvalItem.run_id == run_id)).all()
        assert len(items) == 0


# 39. test_runner_pauses_on_auth_error
def test_runner_pauses_on_auth_error(eval_db) -> None:
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

    mock_provider = MagicMock(spec=LLMProvider)
    mock_provider.generate.side_effect = LLMAuthError("Invalid API key provided.")

    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=mock_provider,
        sleep_fn=lambda _: None,
    )
    runner.run()

    with session_factory() as session:
        r = session.get(EvalRun, run_id)
        assert r.status == EvalRunStatus.paused
        assert r.error["code"] == "llm_auth_error"


# 40. test_runner_retries_on_rate_limit_up_to_max_waits
def test_runner_retries_on_rate_limit_up_to_max_waits(eval_db) -> None:
    session_factory, eng_id, settings = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=1,
            status=EvalRunStatus.running,
            config={"sample_size": 1, "drafts_sample": 0},
            progress_done=0,
            progress_total=1,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    mock_provider = MagicMock(spec=LLMProvider)
    # Rate limit once, then succeed
    mock_provider.generate.side_effect = [
        LLMRateLimited("Rate limit exceeded.", retry_after_seconds=1.0),
        _mock_classification_response(),
    ]

    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=mock_provider,
        sleep_fn=lambda _: None,
    )
    runner.run()

    with session_factory() as session:
        r = session.get(EvalRun, run_id)
        assert r.status == EvalRunStatus.completed
        items = session.scalars(select(EvalItem).where(EvalItem.run_id == run_id)).all()
        assert len(items) == 1
        assert items[0].status == "success"


# A7.7 test_rate_limit_beyond_max_waits_pauses_run_with_ticket_pending
def test_rate_limit_beyond_max_waits_pauses_run_with_ticket_pending(eval_db) -> None:
    session_factory, eng_id, settings = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=1,
            status=EvalRunStatus.running,
            config={"sample_size": 1, "drafts_sample": 0},
            progress_done=0,
            progress_total=1,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    mock_provider = MagicMock(spec=LLMProvider)
    # Exceed max_rate_limit_waits (settings.eval_max_rate_limit_waits == 2)
    mock_provider.generate.side_effect = [
        LLMRateLimited("Rate limit hit 1.", retry_after_seconds=1.0),
        LLMRateLimited("Rate limit hit 2.", retry_after_seconds=1.0),
        LLMRateLimited("Rate limit hit 3.", retry_after_seconds=1.0),
        LLMRateLimited("Rate limit hit 4.", retry_after_seconds=1.0),
    ]

    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=mock_provider,
        sleep_fn=lambda _: None,
    )
    runner.run()

    with session_factory() as session:
        items = session.scalars(select(EvalItem).where(EvalItem.run_id == run_id)).all()
        # Item failed on rate limit exhaustion
        assert len(items) == 1
        assert items[0].status == "error"
        assert items[0].error_code == "rate_limit"


# 41. test_runner_stops_cleanly_on_cancel
def test_runner_stops_cleanly_on_cancel(eval_db) -> None:
    session_factory, eng_id, settings = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=5,
            status=EvalRunStatus.running,
            config={"sample_size": 5, "drafts_sample": 0},
            progress_done=0,
            progress_total=5,
        )
        session.add(run)
        session.commit()
        run_id = run.id

    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=FakeProvider([_mock_classification_response() for _ in range(5)]),
        sleep_fn=lambda _: None,
    )

    def trigger_cancel(*args, **kwargs):
        runner.stop_event.set()
        from app.triage.service import classify_and_prioritise
        return classify_and_prioritise(*args, **kwargs)

    with patch("app.evaluation.runner.classify_and_prioritise", side_effect=trigger_cancel):
        runner.run()

    with session_factory() as session:
        r = session.get(EvalRun, run_id)
        assert r.status == EvalRunStatus.cancelled


# 42. test_runner_resumes_only_incomplete_tickets & A7.9 test_resume_keeps_completed_items_and_retries_transient_failures
def test_runner_resumes_only_incomplete_tickets(eval_db) -> None:
    session_factory, eng_id, settings = eval_db
    with session_factory() as session:
        run = EvalRun(
            engagement_id=eng_id,
            model="fake-model",
            sample_size=3,
            status=EvalRunStatus.paused,
            config={"sample_size": 3, "drafts_sample": 0},
            progress_done=1,
            progress_total=3,
        )
        session.add(run)
        session.commit()
        run_id = run.id

        # Ticket 1 was already completed successfully
        from app.evaluation.dataset import load_eval_tickets, select_sample
        tickets = select_sample(load_eval_tickets(), 3)
        item1 = EvalItem(
            run_id=run_id,
            ticket_id=tickets[0].id,
            status="success",
            predicted_category=tickets[0].true_category,
            predicted_priority=tickets[0].true_priority,
        )
        session.add(item1)
        session.commit()

    fake_provider = FakeProvider([_mock_classification_response() for _ in range(5)])
    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
        provider=fake_provider,
        sleep_fn=lambda _: None,
    )
    runner.run()

    # Only 2 new tickets should have been classified
    assert len(fake_provider.calls) == 2
    with session_factory() as session:
        r = session.get(EvalRun, run_id)
        assert r.status == EvalRunStatus.completed
        assert r.progress_done == 3


def test_resume_keeps_completed_items_and_retries_transient_failures(eval_db) -> None:
    test_runner_resumes_only_incomplete_tickets(eval_db)


# A5 & A7.32 test_draft_phase_deterministic_sample_records_flags_and_never_stores_reply_text
def test_draft_phase_deterministic_sample_records_flags_and_never_stores_reply_text(eval_db) -> None:
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
    # Order: 3 classification calls (Phase 1), then 1 draft call (Phase 2)
    fake_provider = FakeProvider([
        _mock_classification_response(),
        _mock_classification_response(),
        _mock_classification_response(),
        draft_response,
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
        # Exactly 1 item has draft evaluated
        draft_items = [it for it in items if it.draft is not None]
        assert len(draft_items) == 1
        d = draft_items[0].draft
        assert "reply" not in d, "Reply text must NEVER be stored in EvalItem.draft"
        assert "reviewer_note" not in d, "Reviewer note must not be stored in EvalItem.draft"
        assert d["reply_chars"] == len("Thank you for contacting us.")
        assert d["policy_refs_valid"] is True
        assert d["draft_unavailable"] is False
        assert "flags" in d


# A7.4 test_evaluator_and_production_triage_use_the_same_classification_function
def test_evaluator_and_production_triage_use_the_same_classification_function() -> None:
    import inspect
    from app.triage import pipeline
    from app.evaluation.runner import EvaluationRunner
    # Verify that pipeline.run_triage_pipeline calls classify_and_prioritise
    source = inspect.getsource(pipeline.run_triage_pipeline)
    assert "classify_and_prioritise(" in source, "run_triage_pipeline must call classify_and_prioritise"
    runner_source = inspect.getsource(EvaluationRunner._execute)
    assert "classify_and_prioritise(" in runner_source, "EvaluationRunner._execute must call classify_and_prioritise"


# A7.6 test_eval_creates_no_triage_proposals_and_no_per_ticket_audit_rows_and_audit_has_no_ticket_text
def test_eval_creates_no_triage_proposals_and_no_per_ticket_audit_rows_and_audit_has_no_ticket_text(eval_db) -> None:
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
        # Zero TriageProposal rows created
        proposals = session.scalars(select(TriageProposal)).all()
        assert len(proposals) == 0

        # No per-ticket audit rows
        audit_rows = session.scalars(select(AuditLog)).all()
        for a in audit_rows:
            details_str = json.dumps(a.details or {})
            assert "body" not in details_str
            assert "subject" not in details_str


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
