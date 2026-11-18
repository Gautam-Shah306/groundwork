"""Audit log writer helper."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, utc_now

DEFAULT_ACTOR = "Demo operator"


def record_audit_event(
    db: Session,
    *,
    engagement_id: int | None,
    action: str,
    entity_type: str,
    entity_id: int | str,
    details: dict[str, Any] | None = None,
    actor: str = DEFAULT_ACTOR,
) -> AuditLog:
    """Append an AuditLog entry inside the active database transaction."""
    entry = AuditLog(
        engagement_id=engagement_id,
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        details=details or {},
        created_at=utc_now(),
    )
    db.add(entry)
    return entry
