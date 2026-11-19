"""Assistant investigation run endpoints with background execution and live trace persistence."""

from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, sessionmaker

from app.agent.loop import run_investigation
from app.agent.tools import ToolResult, ToolRunContext, build_analysis_tool_registry
from app.api.datasets import _get_active_dataset_id, _get_dataset_or_404
from app.api.health import resolve_settings
from app.config import Settings
from app.db import get_db
from app.llm import LLMNotConfigured, LLMProvider, UnsupportedProvider, get_provider
from app.llm.errors import scrub_secrets
from app.models import (
    AgentRun,
    AgentRunStatus,
    AnswerStatus,
    AuditLog,
    Dataset,
    Engagement,
    utc_now,
)

router = APIRouter(
    prefix="/api/engagements/{engagement_id}/assistant/runs",
    tags=["assistant"],
)

ProviderFactory = Callable[[Settings], LLMProvider]


def get_provider_factory() -> ProviderFactory:
    """Dependency providing the LLM provider factory (overridable in tests)."""
    return get_provider


class CreateAssistantRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=1, max_length=1000)
    dataset_id: int | None = None

    @field_validator("question")
    @classmethod
    def _validate_question(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("Question must not be blank.")
        if len(trimmed) > 1000:
            raise ValueError("Question must be 1000 characters or fewer.")
        return trimmed


class CreateAssistantRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: int
    status: str


class AgentRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    engagement_id: int
    dataset_id: int
    question: str
    status: str
    answer_status: str
    answer_blocks: list[dict[str, Any]]
    tool_trace: list[dict[str, Any]]
    warnings: list[dict[str, Any]]
    error: dict[str, Any] | None
    model: str
    round_trips: int
    usage: dict[str, Any] | None = None
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None


def _serialize_run(run: AgentRun) -> AgentRunResponse:
    return AgentRunResponse(
        id=run.id,
        engagement_id=run.engagement_id,
        dataset_id=run.dataset_id,
        question=run.question,
        status=run.status.value,
        answer_status=run.answer_status.value,
        answer_blocks=list(run.answer_blocks or []),
        tool_trace=list(run.tool_trace or []),
        warnings=list(run.warnings or []),
        error=dict(run.error) if isinstance(run.error, dict) else None,
        model=run.model,
        round_trips=run.round_trips,
        usage=dict(run.usage) if isinstance(run.usage, dict) else None,
        started_at=run.started_at,
        finished_at=run.finished_at,
        duration_ms=run.duration_ms,
    )


def mark_stale_running_runs_failed(session: Session) -> int:
    """Mark any AgentRun left in 'running' state after a restart as failed/interrupted."""
    stale = session.scalars(
        select(AgentRun).where(AgentRun.status == AgentRunStatus.running)
    ).all()
    if not stale:
        return 0
    now = utc_now()
    for run in stale:
        run.status = AgentRunStatus.failed
        run.answer_status = AnswerStatus.none
        run.error = {
            "code": "interrupted",
            "message": (
                "This investigation was interrupted before completion. "
                "Please retry your question."
            ),
        }
        run.finished_at = now
        if run.started_at is not None:
            run.duration_ms = int(round((now - run.started_at).total_seconds() * 1000))
    session.commit()
    return len(stale)


def _get_engagement_or_404(db: Session, engagement_id: int) -> Engagement:
    engagement = db.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Engagement not found.",
        )
    return engagement


def _execute_run_in_background(
    *,
    session_factory: sessionmaker[Session],
    run_id: int,
    engagement_id: int,
    dataset_id: int,
    question: str,
    provider: LLMProvider,
    max_output_tokens: int,
    api_key_secret: str,
) -> None:
    """Run the investigation loop inside an isolated DB session and persist trace updates."""
    db = session_factory()
    try:
        dataset = db.get(Dataset, dataset_id)
        if dataset is None or dataset.engagement_id != engagement_id:
            run = db.get(AgentRun, run_id)
            if run is not None:
                run.status = AgentRunStatus.failed
                run.answer_status = AnswerStatus.none
                run.error = {
                    "code": "dataset_missing",
                    "message": "The dataset bound to this run is no longer available.",
                }
                run.finished_at = utc_now()
                db.commit()
            return

        ctx = ToolRunContext(db=db, engagement_id=engagement_id, dataset=dataset)
        registry = build_analysis_tool_registry(ctx)

        def _persist_trace(trace: list[ToolResult]) -> None:
            run_row = db.get(AgentRun, run_id)
            if run_row is None:
                return
            run_row.tool_trace = [item.model_dump(mode="json") for item in trace]
            db.commit()

        result = run_investigation(
            question=question,
            provider=provider,
            registry=registry,
            max_output_tokens=max_output_tokens,
            on_trace_update=_persist_trace,
        )

        run = db.get(AgentRun, run_id)
        if run is None:
            return

        finished = utc_now()
        run.status = (
            AgentRunStatus.completed
            if result.status == "completed"
            else AgentRunStatus.failed
        )
        run.answer_status = AnswerStatus(result.answer_status)
        run.answer_blocks = list(result.answer_blocks)
        run.tool_trace = [item.model_dump(mode="json") for item in result.tool_trace]
        run.warnings = [w.model_dump(mode="json") for w in result.warnings]
        if result.error is not None:
            err_dict: dict[str, Any] = {
                "code": str(result.error.get("code", "llm_provider_error")),
                "message": scrub_secrets(
                    str(result.error.get("message", "Investigation failed.")),
                    secrets=(api_key_secret,),
                ),
            }
            if "details" in result.error and isinstance(result.error["details"], dict):
                # Ensure ONLY allowed keys such as attempted_tool are stored, never generated text or reasoning
                details = result.error["details"]
                safe_details = {}
                if "attempted_tool" in details and isinstance(details["attempted_tool"], str):
                    safe_details["attempted_tool"] = details["attempted_tool"]
                if safe_details:
                    err_dict["details"] = safe_details
            run.error = err_dict
        else:
            run.error = None
        if result.model:
            run.model = result.model
        run.round_trips = result.round_trips
        run.usage = dict(result.usage) if result.usage else None
        run.finished_at = finished
        run.duration_ms = result.duration_ms
        db.commit()
    except Exception as exc:  # pragma: no cover - defensive worker guard
        try:
            db.rollback()
            run = db.get(AgentRun, run_id)
            if run is not None:
                run.status = AgentRunStatus.failed
                run.answer_status = AnswerStatus.none
                run.error = {
                    "code": "run_execution_error",
                    "message": scrub_secrets(
                        f"Investigation encountered an unexpected error: {exc}",
                        secrets=(api_key_secret,),
                    ),
                }
                run.finished_at = utc_now()
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


@router.post(
    "",
    response_model=CreateAssistantRunResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_assistant_run(
    engagement_id: int,
    payload: CreateAssistantRunRequest,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(resolve_settings),
    provider_factory: ProviderFactory = Depends(get_provider_factory),
) -> CreateAssistantRunResponse:
    """Start a single-turn investigation run asynchronously and return HTTP 202."""
    _get_engagement_or_404(db, engagement_id)

    try:
        provider = provider_factory(settings)
    except (LLMNotConfigured, UnsupportedProvider) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": exc.message},
        ) from None

    if payload.dataset_id is not None:
        dataset = _get_dataset_or_404(db, engagement_id, payload.dataset_id)
    else:
        active_id = _get_active_dataset_id(db, engagement_id)
        if active_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "no_dataset",
                    "message": (
                        "No ticket dataset is loaded for this engagement. "
                        "Upload a CSV or load the sample dataset before starting an investigation."
                    ),
                },
            )
        dataset = _get_dataset_or_404(db, engagement_id, active_id)

    existing_running = db.scalar(
        select(AgentRun.id).where(
            AgentRun.engagement_id == engagement_id,
            AgentRun.status == AgentRunStatus.running,
        )
    )
    if existing_running is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "run_in_progress",
                "message": (
                    "An investigation is already running for this engagement. "
                    "Wait for it to finish before submitting another question."
                ),
            },
        )

    now = utc_now()
    run = AgentRun(
        engagement_id=engagement_id,
        dataset_id=dataset.id,
        question=payload.question,
        status=AgentRunStatus.running,
        answer_status=AnswerStatus.none,
        answer_blocks=[],
        tool_trace=[],
        warnings=[],
        error=None,
        model=provider.model_name or settings.llm_model,
        round_trips=0,
        started_at=now,
    )
    db.add(run)
    db.flush()

    db.add(
        AuditLog(
            engagement_id=engagement_id,
            actor="Demo operator",
            action="assistant_question",
            entity_type="agent_run",
            entity_id=str(run.id),
            details={
                "run_id": run.id,
                "dataset_id": dataset.id,
                "model": run.model,
            },
            created_at=now,
        )
    )
    db.commit()

    session_factory: sessionmaker[Session] = request.app.state.session_factory
    worker = threading.Thread(
        target=_execute_run_in_background,
        kwargs={
            "session_factory": session_factory,
            "run_id": run.id,
            "engagement_id": engagement_id,
            "dataset_id": dataset.id,
            "question": payload.question,
            "provider": provider,
            "max_output_tokens": settings.llm_max_output_tokens,
            "api_key_secret": settings.llm_api_key,
        },
        daemon=True,
    )
    threads: list[threading.Thread] = getattr(
        request.app.state, "assistant_threads", []
    )
    threads = [t for t in threads if t.is_alive()]
    threads.append(worker)
    request.app.state.assistant_threads = threads
    worker.start()

    return CreateAssistantRunResponse(run_id=run.id, status=run.status.value)


@router.get("", response_model=list[AgentRunResponse])
def list_assistant_runs(
    engagement_id: int,
    limit: int = Query(default=10, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[AgentRunResponse]:
    """Return recent investigation runs for an engagement (newest first)."""
    _get_engagement_or_404(db, engagement_id)
    runs = db.scalars(
        select(AgentRun)
        .where(AgentRun.engagement_id == engagement_id)
        .order_by(desc(AgentRun.id))
        .limit(limit)
    ).all()
    return [_serialize_run(r) for r in runs]


@router.get("/{run_id}", response_model=AgentRunResponse)
def get_assistant_run(
    engagement_id: int,
    run_id: int,
    db: Session = Depends(get_db),
) -> AgentRunResponse:
    """Return full status, tool trace, structured blocks, warnings, and error for one run."""
    _get_engagement_or_404(db, engagement_id)
    run = db.get(AgentRun, run_id)
    if run is None or run.engagement_id != engagement_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Assistant run not found.",
        )
    return _serialize_run(run)
