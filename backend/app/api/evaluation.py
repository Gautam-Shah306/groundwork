"""FastAPI router for Agent Evaluation endpoints (B5).

Provides endpoints to trigger, monitor, list, inspect, resume, and cancel evaluation runs.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.health import resolve_settings
from app.audit import record_audit_event
from app.config import Settings
from app.db import get_db
from app.evaluation.dataset import compute_config_fingerprint, load_eval_tickets
from app.evaluation.runner import EvaluationRunner, get_stop_event
from app.models import Engagement, EvalItem, EvalRun, EvalRunStatus, utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/engagements/{engagement_id}/evaluation", tags=["evaluation"])


class CreateEvalRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sample_size: int = Field(default=150, ge=1, le=150)
    model: str | None = None
    drafts_sample: int = Field(default=0, ge=0, le=150)


class EvalRunResponse(BaseModel):
    id: int
    engagement_id: int
    model: str
    sample_size: int
    status: str
    config: dict[str, Any]
    progress_done: int
    progress_total: int
    config_fingerprint: str
    started_at: datetime
    finished_at: datetime | None = None
    created_at: datetime
    usage: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    results: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_orm_model(cls, run: EvalRun) -> EvalRunResponse:
        status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
        return cls(
            id=run.id,
            engagement_id=run.engagement_id,
            model=run.model,
            sample_size=run.sample_size,
            status=status_val,
            config=run.config or {},
            progress_done=run.progress_done,
            progress_total=run.progress_total,
            config_fingerprint=run.config_fingerprint,
            started_at=run.started_at,
            finished_at=run.finished_at,
            created_at=run.created_at,
            usage=run.usage,
            error=run.error,
            results=run.results or {},
        )


class EvalItemResponse(BaseModel):
    id: int
    run_id: int
    ticket_id: str
    status: str
    error_code: str | None = None
    predicted_category: str | None = None
    predicted_secondary: str | None = None
    predicted_signals: list[Any] = Field(default_factory=list)
    flags: list[dict[str, Any]] = Field(default_factory=list)
    predicted_priority: str | None = None
    rule_id: str | None = None
    predicted_queue: str | None = None
    escalation: bool = False
    usage: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0
    provider_calls: int = 0
    draft: dict[str, Any] | None = None
    created_at: datetime

    @classmethod
    def from_orm_model(cls, it: EvalItem) -> EvalItemResponse:
        return cls(
            id=it.id,
            run_id=it.run_id,
            ticket_id=it.ticket_id,
            status=it.status,
            error_code=it.error_code,
            predicted_category=it.predicted_category,
            predicted_secondary=it.predicted_secondary,
            predicted_signals=it.predicted_signals or [],
            flags=it.flags or [],
            predicted_priority=it.predicted_priority,
            rule_id=it.rule_id,
            predicted_queue=it.predicted_queue,
            escalation=it.escalation,
            usage=it.usage or {},
            duration_ms=it.duration_ms,
            provider_calls=it.provider_calls,
            draft=it.draft,
            created_at=it.created_at,
        )


class EvalItemsListResponse(BaseModel):
    items: list[EvalItemResponse]
    total: int
    page: int
    page_size: int


def _get_engagement_or_404(db: Session, engagement_id: int) -> Engagement:
    eng = db.get(Engagement, engagement_id)
    if not eng:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engagement {engagement_id} not found.",
        )
    return eng


def _get_run_or_404(db: Session, engagement_id: int, run_id: int) -> EvalRun:
    _get_engagement_or_404(db, engagement_id)
    run_obj = db.get(EvalRun, run_id)
    if not run_obj or run_obj.engagement_id != engagement_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"EvalRun {run_id} not found for engagement {engagement_id}.",
        )
    return run_obj


def _start_runner_thread(
    request: Request,
    run_id: int,
    settings: Settings,
) -> None:
    session_factory = request.app.state.session_factory
    runner = EvaluationRunner(
        session_factory=session_factory,
        run_id=run_id,
        settings=settings,
    )
    thread = threading.Thread(
        target=runner.run,
        daemon=True,
        name=f"eval-runner-{run_id}",
    )
    if not hasattr(request.app.state, "eval_threads"):
        request.app.state.eval_threads = []
    request.app.state.eval_threads.append(thread)
    thread.start()


@router.post("/runs", response_model=EvalRunResponse, status_code=status.HTTP_201_CREATED)
def create_eval_run(
    engagement_id: int,
    payload: CreateEvalRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(resolve_settings),
) -> Any:
    """Trigger a new triage evaluation benchmark run."""
    _get_engagement_or_404(db, engagement_id)

    # Check if another run is in progress
    active = db.scalar(
        select(EvalRun).where(
            EvalRun.engagement_id == engagement_id,
            EvalRun.status == EvalRunStatus.running,
        )
    )
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "run_already_in_progress",
                "message": f"Run {active.id} is already in progress for this engagement.",
            },
        )

    resolved_model = payload.model or settings.llm_model or "unknown"
    fingerprint = compute_config_fingerprint(
        model=resolved_model,
        temperature=0.0,
        max_output_tokens=settings.llm_triage_max_output_tokens,
    )

    run_config = {
        "sample_size": payload.sample_size,
        "drafts_sample": payload.drafts_sample,
        "model": resolved_model,
        "pacing_seconds": settings.eval_pacing_seconds,
    }

    eval_run = EvalRun(
        engagement_id=engagement_id,
        model=resolved_model,
        sample_size=payload.sample_size,
        status=EvalRunStatus.running,
        config=run_config,
        progress_done=0,
        progress_total=payload.sample_size,
        config_fingerprint=fingerprint,
        results={},
        started_at=utc_now(),
    )
    db.add(eval_run)
    db.commit()
    db.refresh(eval_run)

    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="eval_run_started",
        entity_type="eval_run",
        entity_id=str(eval_run.id),
        details={
            "run_id": eval_run.id,
            "sample_size": payload.sample_size,
            "drafts_sample": payload.drafts_sample,
            "model": resolved_model,
        },
    )
    db.commit()

    _start_runner_thread(request, eval_run.id, settings)
    return EvalRunResponse.from_orm_model(eval_run)


@router.get("/runs", response_model=list[EvalRunResponse])
def list_eval_runs(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """List all evaluation runs for the engagement, newest first."""
    _get_engagement_or_404(db, engagement_id)
    runs = db.scalars(
        select(EvalRun)
        .where(EvalRun.engagement_id == engagement_id)
        .order_by(EvalRun.id.desc())
    ).all()
    return [EvalRunResponse.from_orm_model(r) for r in runs]


@router.get("/runs/{run_id}", response_model=EvalRunResponse)
def get_eval_run(
    engagement_id: int,
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Retrieve details, progress, or metrics of a specific evaluation run."""
    run_obj = _get_run_or_404(db, engagement_id, run_id)
    return EvalRunResponse.from_orm_model(run_obj)


@router.get("/runs/{run_id}/items", response_model=EvalItemsListResponse)
def get_eval_run_items(
    engagement_id: int,
    run_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=150),
    status_filter: str | None = Query(default=None, alias="status"),
    failure_only: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Any:
    """Get paginated ticket items for an evaluation run with optional filtering."""
    run_obj = _get_run_or_404(db, engagement_id, run_id)

    query = select(EvalItem).where(EvalItem.run_id == run_id)
    if status_filter:
        query = query.where(EvalItem.status == status_filter)

    items = db.scalars(query.order_by(EvalItem.id.asc())).all()

    # If failure_only requested, load test tickets to determine mismatches
    if failure_only:
        try:
            tickets = load_eval_tickets()
            ticket_map = {t.id: t for t in tickets}
            filtered: list[EvalItem] = []
            for it in items:
                if it.status != "success":
                    filtered.append(it)
                    continue
                t = ticket_map.get(it.ticket_id)
                if t:
                    if it.predicted_category != t.true_category or it.predicted_priority != t.true_priority:
                        filtered.append(it)
                else:
                    filtered.append(it)
            items = filtered
        except Exception as exc:
            logger.warning("Failed to load eval tickets for failure_only filter: %s", exc)

    total_count = len(items)
    start_idx = (page - 1) * page_size
    paged_items = items[start_idx : start_idx + page_size]

    return EvalItemsListResponse(
        items=[EvalItemResponse.from_orm_model(it) for it in paged_items],
        total=total_count,
        page=page,
        page_size=page_size,
    )


@router.post("/runs/{run_id}/resume", response_model=EvalRunResponse)
def resume_eval_run(
    engagement_id: int,
    run_id: int,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(resolve_settings),
) -> Any:
    """Resume a paused, interrupted, or failed evaluation run."""
    run_obj = _get_run_or_404(db, engagement_id, run_id)

    if run_obj.status == EvalRunStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Completed run cannot be resumed.",
        )

    # Check if another run is currently running
    active = db.scalar(
        select(EvalRun).where(
            EvalRun.engagement_id == engagement_id,
            EvalRun.status == EvalRunStatus.running,
            EvalRun.id != run_id,
        )
    )
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "run_already_in_progress",
                "message": f"Run {active.id} is currently running for this engagement.",
            },
        )

    run_obj.status = EvalRunStatus.running
    run_obj.error = None
    db.commit()
    db.refresh(run_obj)

    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="eval_run_resumed",
        entity_type="eval_run",
        entity_id=str(run_obj.id),
        details={"run_id": run_obj.id},
    )
    db.commit()

    _start_runner_thread(request, run_obj.id, settings)
    return EvalRunResponse.from_orm_model(run_obj)


@router.post("/runs/{run_id}/cancel", response_model=EvalRunResponse)
def cancel_eval_run(
    engagement_id: int,
    run_id: int,
    db: Session = Depends(get_db),
) -> Any:
    """Cancel a running evaluation run."""
    run_obj = _get_run_or_404(db, engagement_id, run_id)

    if run_obj.status in (EvalRunStatus.completed, EvalRunStatus.cancelled):
        return EvalRunResponse.from_orm_model(run_obj)

    # Signal stop event to background runner
    stop_ev = get_stop_event(run_id)
    stop_ev.set()

    run_obj.status = EvalRunStatus.cancelled
    db.commit()
    db.refresh(run_obj)

    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="eval_run_cancelled",
        entity_type="eval_run",
        entity_id=str(run_obj.id),
        details={"run_id": run_obj.id},
    )
    db.commit()

    return EvalRunResponse.from_orm_model(run_obj)
