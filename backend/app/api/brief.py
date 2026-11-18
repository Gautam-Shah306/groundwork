"""Problem brief endpoints scoped to an engagement."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.engagements import get_engagement_or_404
from app.audit import record_audit_event
from app.db import get_db
from app.models import ProblemBrief, utc_now
from app.schemas import BriefResponse, BriefUpsert

router = APIRouter(prefix="/api/engagements/{engagement_id}/brief", tags=["brief"])


@router.get("", response_model=BriefResponse)
def get_brief(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> BriefResponse:
    """Return the engagement's problem brief or 404 when none exists yet."""
    get_engagement_or_404(db, engagement_id)
    brief = db.scalar(
        select(ProblemBrief).where(ProblemBrief.engagement_id == engagement_id)
    )
    if brief is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No problem brief exists for engagement {engagement_id} yet.",
        )
    return BriefResponse.from_orm_model(brief)


@router.put("", response_model=BriefResponse)
def upsert_brief(
    engagement_id: int,
    payload: BriefUpsert,
    db: Session = Depends(get_db),
) -> BriefResponse:
    """Create or update the engagement's problem brief and record an audit entry."""
    get_engagement_or_404(db, engagement_id)
    brief = db.scalar(
        select(ProblemBrief).where(ProblemBrief.engagement_id == engagement_id)
    )
    now = utc_now()

    if brief is None:
        brief = ProblemBrief(
            engagement_id=engagement_id,
            sections=dict(payload.sections),
            source=payload.source,
            updated_at=now,
        )
        db.add(brief)
        db.flush()
        action = "create"
    else:
        brief.sections = dict(payload.sections)
        brief.source = payload.source
        brief.updated_at = now
        action = "update"

    record_audit_event(
        db,
        engagement_id=engagement_id,
        action=action,
        entity_type="brief",
        entity_id=brief.id,
        details={"source": brief.source.value, "sections": sorted(brief.sections.keys())},
    )
    db.commit()
    db.refresh(brief)
    return BriefResponse.from_orm_model(brief)
