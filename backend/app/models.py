"""SQLAlchemy ORM table models for Groundwork persistence."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


class UTCDateTime(TypeDecorator):
    """Store UTC datetimes in SQLite and always return timezone-aware UTC values."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def process_result_value(self, value: datetime | None, dialect: Any) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


class EngagementStage(str, enum.Enum):
    discover = "discover"
    diagnose = "diagnose"
    build = "build"
    measure = "measure"


class BriefSource(str, enum.Enum):
    ai_draft = "ai_draft"
    edited = "edited"


class ProposalStatus(str, enum.Enum):
    awaiting_approval = "awaiting_approval"
    approved = "approved"
    rejected = "rejected"


class Base(DeclarativeBase):
    """Declarative base for all Groundwork tables."""


class Engagement(Base):
    __tablename__ = "engagements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    client_name: Mapped[str] = mapped_column(String(120), nullable=False)
    industry: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    client_statement: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stage: Mapped[EngagementStage] = mapped_column(
        SAEnum(EngagementStage, native_enum=False),
        nullable=False,
        default=EngagementStage.discover,
    )
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    notes: Mapped[list[InterviewNote]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    brief: Mapped[ProblemBrief | None] = relationship(
        back_populates="engagement",
        uselist=False,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    datasets: Mapped[list[Dataset]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    tickets: Mapped[list[Ticket]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    triage_proposals: Mapped[list[TriageProposal]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    kpis: Mapped[list[Kpi]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    eval_runs: Mapped[list[EvalRun]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    pilot_simulations: Mapped[list[PilotSimulation]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class InterviewNote(Base):
    __tablename__ = "interview_notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    engagement: Mapped[Engagement] = relationship(back_populates="notes")


class ProblemBrief(Base):
    __tablename__ = "problem_briefs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    sections: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[BriefSource] = mapped_column(
        SAEnum(BriefSource, native_enum=False),
        nullable=False,
        default=BriefSource.edited,
    )
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    engagement: Mapped[Engagement] = relationship(back_populates="brief")


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    period_start: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    period_end: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    validation_report: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    engagement: Mapped[Engagement] = relationship(back_populates="datasets")
    tickets: Mapped[list[Ticket]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Ticket(Base):
    __tablename__ = "tickets"

    ticket_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        primary_key=True,
    )
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    assigned_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    first_response_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(60), nullable=True)
    queue: Mapped[str | None] = mapped_column(String(120), nullable=True)
    assigned_agent: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str | None] = mapped_column(String(60), nullable=True)
    channel: Mapped[str | None] = mapped_column(String(60), nullable=True)
    reassignment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    customer_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_valid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    validation_flags: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)

    engagement: Mapped[Engagement] = relationship(back_populates="tickets")
    dataset: Mapped[Dataset] = relationship(back_populates="tickets")


class TriageProposal(Base):
    __tablename__ = "triage_proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_text: Mapped[str] = mapped_column(Text, nullable=False)
    proposed_category: Mapped[str] = mapped_column(String(120), nullable=False)
    proposed_priority: Mapped[str] = mapped_column(String(60), nullable=False)
    proposed_queue: Mapped[str] = mapped_column(String(120), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    rule_fired: Mapped[str | None] = mapped_column(String(200), nullable=True)
    draft_reply: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[ProposalStatus] = mapped_column(
        SAEnum(ProposalStatus, native_enum=False),
        nullable=False,
        default=ProposalStatus.awaiting_approval,
    )
    final_values: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    engagement: Mapped[Engagement] = relationship(back_populates="triage_proposals")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(120), nullable=False)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(60), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(120), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)


class Kpi(Base):
    __tablename__ = "kpis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    calculation: Mapped[str] = mapped_column(Text, nullable=False)
    baseline: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    target: Mapped[str | None] = mapped_column(String(120), nullable=True)
    target_assumption: Mapped[str | None] = mapped_column(Text, nullable=True)
    period: Mapped[str | None] = mapped_column(String(120), nullable=True)
    data_source: Mapped[str | None] = mapped_column(String(200), nullable=True)
    owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    caveats: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    engagement: Mapped[Engagement] = relationship(back_populates="kpis")


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    engagement: Mapped[Engagement] = relationship(back_populates="eval_runs")


class PilotSimulation(Base):
    __tablename__ = "pilot_simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    engagement: Mapped[Engagement] = relationship(back_populates="pilot_simulations")
