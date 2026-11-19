"""Discovery analysis and draft application endpoints scoped to an engagement."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.engagements import get_engagement_or_404
from app.api.health import resolve_settings
from app.audit import record_audit_event
from app.config import Settings
from app.db import get_db
from app.discovery.service import (
    MAX_COMBINED_NOTES_CHARS,
    execute_discovery_analysis,
    record_brief_version,
)
from app.llm.base import LLMProvider
from app.llm.errors import LLMError, LLMNotConfigured, LLMOutputTruncated, UnsupportedProvider, scrub_secrets
from app.llm.factory import get_provider
from app.models import BriefSource, DiscoveryAnalysis, InterviewNote, ProblemBrief, utc_now
from app.schemas import BriefResponse, DiscoveryAnalysisResponse

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/engagements/{engagement_id}/discovery",
    tags=["discovery"],
)


class AnalyseNotesRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note_ids: list[int] | None = None


class ApplyAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm_replace: bool = Field(default=False)


@router.post("/analyse", response_model=DiscoveryAnalysisResponse)
def analyse_notes_endpoint(
    engagement_id: int,
    payload: AnalyseNotesRequest | None = None,
    db: Session = Depends(get_db),
    settings: Settings = Depends(resolve_settings),
) -> DiscoveryAnalysisResponse:
    """Run synchronous discovery analysis over selected interview notes."""
    engagement = get_engagement_or_404(db, engagement_id)

    if not settings.llm_configured:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "llm_not_configured",
                "message": (
                    "LLM provider is not configured. Set LLM_API_KEY and LLM_MODEL in .env "
                    "and restart the backend to enable AI discovery analysis."
                ),
            },
        )

    # Fetch notes
    query = select(InterviewNote).where(InterviewNote.engagement_id == engagement_id)
    if payload and payload.note_ids:
        query = query.where(InterviewNote.id.in_(payload.note_ids))
    notes = list(db.scalars(query.order_by(InterviewNote.created_at.asc())).all())

    if not notes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "no_notes",
                "message": "At least one interview note is required for discovery analysis.",
            },
        )

    total_chars = sum(len(n.title or "") + len(n.content or "") for n in notes)
    if total_chars > MAX_COMBINED_NOTES_CHARS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "notes_too_large",
                "message": (
                    f"Selected notes contain {total_chars} characters, exceeding the 30,000 character limit. "
                    "Please select fewer notes or trim verbose interview content."
                ),
            },
        )

    try:
        provider = get_provider(settings)
    except (LLMNotConfigured, UnsupportedProvider) as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    try:
        analysis = execute_discovery_analysis(
            db=db,
            engagement=engagement,
            notes=notes,
            provider=provider,
            max_output_tokens=settings.llm_discovery_max_output_tokens,
            api_key_secret=settings.llm_api_key,
        )
        return DiscoveryAnalysisResponse.from_orm_model(analysis)
    except LLMOutputTruncated as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except (LLMError, Exception) as exc:
        code = getattr(exc, "code", "llm_provider_error")
        msg = scrub_secrets(str(exc), secrets=(settings.llm_api_key,))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": code, "message": msg},
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "validation_error", "message": str(exc)},
        ) from exc


@router.get("/analyses", response_model=list[DiscoveryAnalysisResponse])
def list_analyses_endpoint(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> list[DiscoveryAnalysisResponse]:
    """List up to 10 most recent discovery analyses for the engagement (newest first)."""
    get_engagement_or_404(db, engagement_id)
    analyses = (
        db.scalars(
            select(DiscoveryAnalysis)
            .where(DiscoveryAnalysis.engagement_id == engagement_id)
            .order_by(DiscoveryAnalysis.created_at.desc(), DiscoveryAnalysis.id.desc())
            .limit(10)
        )
        .all()
    )
    return [DiscoveryAnalysisResponse.from_orm_model(a) for a in analyses]


@router.get("/analyses/{analysis_id}", response_model=DiscoveryAnalysisResponse)
def get_analysis_endpoint(
    engagement_id: int,
    analysis_id: int,
    db: Session = Depends(get_db),
) -> DiscoveryAnalysisResponse:
    """Get a specific discovery analysis by id."""
    get_engagement_or_404(db, engagement_id)
    analysis = db.get(DiscoveryAnalysis, analysis_id)
    if analysis is None or analysis.engagement_id != engagement_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis {analysis_id} not found for engagement {engagement_id}.",
        )
    return DiscoveryAnalysisResponse.from_orm_model(analysis)


@router.post("/analyses/{analysis_id}/apply", response_model=BriefResponse)
def apply_analysis_endpoint(
    engagement_id: int,
    analysis_id: int,
    payload: ApplyAnalysisRequest | None = None,
    db: Session = Depends(get_db),
) -> BriefResponse:
    """Apply an AI discovery analysis draft as the current problem brief."""
    get_engagement_or_404(db, engagement_id)
    analysis = db.get(DiscoveryAnalysis, analysis_id)
    if analysis is None or analysis.engagement_id != engagement_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Analysis {analysis_id} not found for engagement {engagement_id}.",
        )

    if analysis.status != "completed" or not analysis.draft:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "code": "invalid_analysis",
                "message": "Only successfully completed analyses with a draft can be applied.",
            },
        )

    confirm_replace = payload.confirm_replace if payload else False
    brief = db.scalar(
        select(ProblemBrief).where(ProblemBrief.engagement_id == engagement_id)
    )

    if (
        brief is not None
        and brief.source == BriefSource.edited
        and not confirm_replace
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "would_overwrite_edits",
                "message": (
                    "Applying this AI draft will overwrite manual edits. "
                    "Confirm replacement to proceed (your current brief will be saved to version history)."
                ),
            },
        )

    now = utc_now()
    if brief is None:
        brief = ProblemBrief(
            engagement_id=engagement_id,
            sections=dict(analysis.draft),
            source=BriefSource.ai_draft,
            updated_at=now,
        )
        db.add(brief)
        db.flush()
    else:
        brief.sections = dict(analysis.draft)
        brief.source = BriefSource.ai_draft
        brief.updated_at = now

    record_brief_version(
        db,
        engagement_id=engagement_id,
        sections=dict(analysis.draft),
        source="ai_draft",
        reason="apply",
    )
    analysis.applied_at = now

    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="apply_analysis",
        entity_type="brief",
        entity_id=brief.id,
        details={"analysis_id": analysis.id, "source": "ai_draft"},
    )

    db.commit()
    db.refresh(brief)
    return BriefResponse.from_orm_model(brief)
