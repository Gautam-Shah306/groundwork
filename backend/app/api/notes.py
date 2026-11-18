"""Interview note endpoints scoped to an engagement."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.engagements import get_engagement_or_404
from app.audit import record_audit_event
from app.db import get_db
from app.models import InterviewNote, utc_now
from app.schemas import NoteCreate, NoteResponse, NoteUpdate

router = APIRouter(prefix="/api/engagements/{engagement_id}/notes", tags=["notes"])


def _get_note_or_404(db: Session, engagement_id: int, note_id: int) -> InterviewNote:
    note = db.scalar(
        select(InterviewNote).where(
            InterviewNote.id == note_id,
            InterviewNote.engagement_id == engagement_id,
        )
    )
    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note {note_id} not found for engagement {engagement_id}.",
        )
    return note


@router.get("", response_model=list[NoteResponse])
def list_notes(
    engagement_id: int,
    db: Session = Depends(get_db),
) -> list[NoteResponse]:
    """List interview notes for an engagement ordered oldest to newest."""
    get_engagement_or_404(db, engagement_id)
    notes = db.scalars(
        select(InterviewNote)
        .where(InterviewNote.engagement_id == engagement_id)
        .order_by(InterviewNote.created_at.asc(), InterviewNote.id.asc())
    ).all()
    return [NoteResponse.from_orm_model(note) for note in notes]


@router.post("", response_model=NoteResponse, status_code=status.HTTP_201_CREATED)
def create_note(
    engagement_id: int,
    payload: NoteCreate,
    db: Session = Depends(get_db),
) -> NoteResponse:
    """Create an interview note for an engagement and log the event."""
    get_engagement_or_404(db, engagement_id)
    note = InterviewNote(
        engagement_id=engagement_id,
        title=payload.title,
        content=payload.content,
        created_at=utc_now(),
    )
    db.add(note)
    db.flush()

    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="create",
        entity_type="note",
        entity_id=note.id,
        details={"title": note.title},
    )
    db.commit()
    db.refresh(note)
    return NoteResponse.from_orm_model(note)


@router.put("/{note_id}", response_model=NoteResponse)
def update_note(
    engagement_id: int,
    note_id: int,
    payload: NoteUpdate,
    db: Session = Depends(get_db),
) -> NoteResponse:
    """Update an interview note and record an audit log row."""
    get_engagement_or_404(db, engagement_id)
    note = _get_note_or_404(db, engagement_id, note_id)
    changes = payload.model_dump(exclude_unset=True)

    for field_name, field_value in changes.items():
        setattr(note, field_name, field_value)

    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="update",
        entity_type="note",
        entity_id=note.id,
        details={"title": note.title, "fields": sorted(changes.keys())},
    )
    db.commit()
    db.refresh(note)
    return NoteResponse.from_orm_model(note)


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    engagement_id: int,
    note_id: int,
    db: Session = Depends(get_db),
) -> Response:
    """Delete an interview note and record an audit log row."""
    get_engagement_or_404(db, engagement_id)
    note = _get_note_or_404(db, engagement_id, note_id)
    title = note.title

    db.delete(note)
    record_audit_event(
        db,
        engagement_id=engagement_id,
        action="delete",
        entity_type="note",
        entity_id=note_id,
        details={"title": title},
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
