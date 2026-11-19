"""Problem brief endpoints scoped to an engagement."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.engagements import get_engagement_or_404
from app.audit import record_audit_event
from app.db import get_db
from app.discovery.service import record_brief_version
from app.models import BriefSource, BriefVersion, ProblemBrief, utc_now
from app.schemas import BriefResponse, BriefUpsert, BriefVersionResponse

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
    sections_dict = payload.sections.model_dump(mode="json")

    if brief is None:
        brief = ProblemBrief(
            engagement_id=engagement_id,
            sections=sections_dict,
            source=BriefSource.edited,
            updated_at=now,
        )
        db.add(brief)
        db.flush()
        action = "create"
    else:
        brief.sections = sections_dict
        brief.source = BriefSource.edited
        brief.updated_at = now
        action = "update"

    record_brief_version(
        db,
        engagement_id=engagement_id,
        sections=sections_dict,
        source="edited",
        reason="edit",
    )
    record_audit_event(
        db,
        engagement_id=engagement_id,
        action=action,
        entity_type="brief",
        entity_id=brief.id,
        details={"source": BriefSource.edited.value, "sections": sorted(brief.sections.keys())},
    )
    db.commit()
    db.refresh(brief)
    return BriefResponse.from_orm_model(brief)


@router.get("/versions", response_model=list[BriefVersionResponse])
def get_brief_versions(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> list[BriefVersionResponse]:
    """Return the engagement's brief version history (up to 5, newest first)."""
    get_engagement_or_404(db, engagement_id)
    versions = (
        db.scalars(
            select(BriefVersion)
            .where(BriefVersion.engagement_id == engagement_id)
            .order_by(BriefVersion.saved_at.desc(), BriefVersion.id.desc())
        )
        .all()
    )
    return [BriefVersionResponse.from_orm_model(v) for v in versions]


@router.post("/versions/{version_id}/restore", response_model=BriefResponse)
def restore_brief_version(
    engagement_id: int,
    version_id: int,
    db: Session = Depends(get_db),
) -> BriefResponse:
    """Restore a previous brief version snapshot and record an audit entry."""
    get_engagement_or_404(db, engagement_id)
    version = db.get(BriefVersion, version_id)
    if version is None or version.engagement_id != engagement_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Version {version_id} not found for engagement {engagement_id}.",
        )

    brief = db.scalar(
        select(ProblemBrief).where(ProblemBrief.engagement_id == engagement_id)
    )
    now = utc_now()
    if brief is None:
        brief = ProblemBrief(
            engagement_id=engagement_id,
            sections=dict(version.sections),
            source=BriefSource.edited,
            updated_at=now,
        )
        db.add(brief)
        db.flush()
    else:
        brief.sections = dict(version.sections)
        brief.source = BriefSource.edited
        brief.updated_at = now

    record_brief_version(
        db,
        engagement_id=engagement_id,
        sections=dict(version.sections),
        source="edited",
        reason="restore",
    )
    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="restore",
        entity_type="brief",
        entity_id=brief.id,
        details={"restored_version_id": version.id, "reason": "restore"},
    )
    db.commit()
    db.refresh(brief)
    return BriefResponse.from_orm_model(brief)
