"""Activity feed endpoint backed by the engagement audit log."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.engagements import get_engagement_or_404
from app.db import get_db
from app.models import AuditLog
from app.schemas import AuditLogResponse

router = APIRouter(prefix="/api/engagements/{engagement_id}/activity", tags=["activity"])


@router.get("", response_model=list[AuditLogResponse])
def get_activity(
    engagement_id: int,
    limit: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
) -> list[AuditLogResponse]:
    """Return latest audit log entries for an engagement, newest first."""
    get_engagement_or_404(db, engagement_id)
    entries = db.scalars(
        select(AuditLog)
        .where(AuditLog.engagement_id == engagement_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(limit)
    ).all()
    return [AuditLogResponse.from_orm_model(entry) for entry in entries]
