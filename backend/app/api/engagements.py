"""Engagement CRUD API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import record_audit_event
from app.db import get_db
from app.models import Engagement, utc_now
from app.schemas import EngagementCreate, EngagementResponse, EngagementUpdate

router = APIRouter(prefix="/api/engagements", tags=["engagements"])


def get_engagement_or_404(db: Session, engagement_id: int) -> Engagement:
    """Fetch an engagement by primary key or raise HTTP 404."""
    engagement = db.get(Engagement, engagement_id)
    if engagement is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engagement {engagement_id} not found.",
        )
    return engagement


@router.get("", response_model=list[EngagementResponse])
def list_engagements(db: Session = Depends(get_db)) -> list[EngagementResponse]:
    """Return all engagements ordered deterministically by creation order."""
    rows = db.scalars(select(Engagement).order_by(Engagement.id.asc())).all()
    return [EngagementResponse.from_orm_model(row) for row in rows]


@router.post("", response_model=EngagementResponse, status_code=status.HTTP_201_CREATED)
def create_engagement(
    payload: EngagementCreate,
    db: Session = Depends(get_db),
) -> EngagementResponse:
    """Create a new engagement and write an audit log entry."""
    now = utc_now()
    engagement = Engagement(
        name=payload.name,
        client_name=payload.client_name,
        industry=payload.industry,
        client_statement=payload.client_statement,
        stage=payload.stage,
        is_synthetic=payload.is_synthetic,
        created_at=now,
        updated_at=now,
    )
    db.add(engagement)
    db.flush()

    record_audit_event(
        db,
        engagement_id=engagement.id,
        action="create",
        entity_type="engagement",
        entity_id=engagement.id,
        details={"name": engagement.name, "client_name": engagement.client_name},
    )
    db.commit()
    db.refresh(engagement)
    return EngagementResponse.from_orm_model(engagement)


@router.get("/{engagement_id}", response_model=EngagementResponse)
def get_engagement(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> EngagementResponse:
    """Return a single engagement by ID."""
    engagement = get_engagement_or_404(db, engagement_id)
    return EngagementResponse.from_orm_model(engagement)


@router.patch("/{engagement_id}", response_model=EngagementResponse)
def update_engagement(
    engagement_id: int,
    payload: EngagementUpdate,
    db: Session = Depends(get_db),
) -> EngagementResponse:
    """Partially update an engagement, bump updated_at, and record audit history."""
    engagement = get_engagement_or_404(db, engagement_id)
    changes = payload.model_dump(exclude_unset=True)

    for field_name, field_value in changes.items():
        setattr(engagement, field_name, field_value)

    engagement.updated_at = utc_now()
    record_audit_event(
        db,
        engagement_id=engagement.id,
        action="update",
        entity_type="engagement",
        entity_id=engagement.id,
        details={
            "name": engagement.name,
            "fields": sorted(changes.keys()),
        },
    )
    db.commit()
    db.refresh(engagement)
    return EngagementResponse.from_orm_model(engagement)


@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_engagement(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete an engagement, cascade to child rows, and preserve an audit record."""
    engagement = get_engagement_or_404(db, engagement_id)
    snapshot = {"name": engagement.name, "client_name": engagement.client_name}

    db.delete(engagement)
    db.flush()

    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="delete",
        entity_type="engagement",
        entity_id=engagement_id,
        details=snapshot,
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
