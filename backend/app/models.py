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
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    TypeDecorator,
    UniqueConstraint,
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


class AgentRunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"


class AnswerStatus(str, enum.Enum):
    structured = "structured"
    unstructured = "unstructured"
    none = "none"


class EvalRunStatus(str, enum.Enum):
    running = "running"
    paused = "paused"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class Base(DeclarativeBase):
    """Declarative base for all Groundwork tables."""


class Engagement(Base):
    __tablename__ = "engagements"
    __table_args__ = {"sqlite_autoincrement": True}

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
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    brief_versions: Mapped[list[BriefVersion]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    discovery_analyses: Mapped[list[DiscoveryAnalysis]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    interventions: Mapped[list[Intervention]] = relationship(
        back_populates="engagement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    outcome_review: Mapped[OutcomeReview | None] = relationship(
        back_populates="engagement",
        uselist=False,
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


class BriefVersion(Base):
    __tablename__ = "brief_versions"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sections: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)  # apply | edit | restore
    saved_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    engagement: Mapped[Engagement] = relationship(back_populates="brief_versions")


class DiscoveryAnalysis(Base):
    __tablename__ = "discovery_analyses"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    note_ids: Mapped[list[int] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)  # completed | failed
    draft: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    notes_chars: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    applied_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    engagement: Mapped[Engagement] = relationship(back_populates="discovery_analyses")


class Dataset(Base):
    __tablename__ = "datasets"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    is_sample: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
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
    __table_args__ = {"sqlite_autoincrement": True}

    row_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_id: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
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
    validation_flags: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)

    engagement: Mapped[Engagement] = relationship(back_populates="tickets")
    dataset: Mapped[Dataset] = relationship(back_populates="tickets")


class TriageProposal(Base):
    __tablename__ = "triage_proposals"
    __table_args__ = (
        UniqueConstraint("engagement_id", "ticket_hash", name="uq_triage_proposals_eng_ticket_hash"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ticket_text: Mapped[str] = mapped_column(Text, nullable=False)
    channel: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ticket_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    proposed_category: Mapped[str] = mapped_column(String(120), nullable=False)
    secondary_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    proposed_priority: Mapped[str] = mapped_column(String(60), nullable=False)
    proposed_queue: Mapped[str] = mapped_column(String(120), nullable=False)
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    rationale: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rule_fired: Mapped[str | None] = mapped_column(String(200), nullable=True)
    signals: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    flags: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    tool_trace: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON, nullable=True)
    draft_reply: Mapped[str] = mapped_column(Text, nullable=False)
    policy_refs: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    reviewer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    status: Mapped[ProposalStatus] = mapped_column(
        SAEnum(ProposalStatus, native_enum=False),
        nullable=False,
        default=ProposalStatus.awaiting_approval,
    )
    final_values: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(120), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    edited: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    decided_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    engagement: Mapped[Engagement] = relationship(back_populates="triage_proposals")

    @property
    def body(self) -> str:
        return self.ticket_text

    @property
    def category(self) -> str:
        return self.proposed_category

    @property
    def priority(self) -> str:
        return self.proposed_priority

    @property
    def queue(self) -> str:
        return self.proposed_queue


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

    # Outcomes extensions
    metric_id: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    direction: Mapped[str] = mapped_column(String(32), nullable=False, default="lower_is_better")
    baseline_dataset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")

    engagement: Mapped[Engagement] = relationship(back_populates="kpis")


class EvalRun(Base):
    __tablename__ = "eval_runs"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    sample_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[EvalRunStatus] = mapped_column(
        SAEnum(EvalRunStatus, native_enum=False),
        nullable=False,
        default=EvalRunStatus.running,
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    progress_done: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    progress_total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    config_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    engagement: Mapped[Engagement] = relationship(back_populates="eval_runs")
    items: Mapped[list[EvalItem]] = relationship(
        back_populates="run",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class EvalItem(Base):
    __tablename__ = "eval_items"
    __table_args__ = (
        UniqueConstraint("run_id", "ticket_id", name="uq_eval_items_run_ticket"),
        {"sqlite_autoincrement": True},
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_id: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="success")
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    predicted_category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    predicted_secondary: Mapped[str | None] = mapped_column(String(120), nullable=True)
    predicted_signals: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    flags: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    predicted_priority: Mapped[str | None] = mapped_column(String(60), nullable=True)
    rule_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    predicted_queue: Mapped[str | None] = mapped_column(String(120), nullable=True)
    escalation: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    usage: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    provider_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    draft: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    run: Mapped[EvalRun] = relationship(back_populates="items")


class PilotSimulation(Base):
    __tablename__ = "pilot_simulations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eval_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    seed: Mapped[int] = mapped_column(Integer, nullable=False, default=42)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    results: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    results_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    engagement: Mapped[Engagement] = relationship(back_populates="pilot_simulations")


class Intervention(Base):
    __tablename__ = "interventions"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    impact: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    effort: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    risk: Mapped[int] = mapped_column(Integer, nullable=False)    # 1-5
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")  # proposed|selected|rejected
    origin: Mapped[str] = mapped_column(String(32), nullable=False, default="seeded")    # seeded|human
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    engagement: Mapped[Engagement] = relationship(back_populates="interventions")


class OutcomeReview(Base):
    __tablename__ = "outcome_reviews"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    sections: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="ai_draft")  # ai_draft|edited
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")     # draft|confirmed
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    flags: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    final_recommendation: Mapped[str | None] = mapped_column(String(32), nullable=True)  # continue|modify|expand|stop
    acknowledged_simulated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)

    engagement: Mapped[Engagement] = relationship(back_populates="outcome_review")



class AgentRun(Base):
    __tablename__ = "agent_runs"
    __table_args__ = {"sqlite_autoincrement": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    engagement_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Intentionally NOT a cascading FK so deleting a Dataset retains its historical runs.
    dataset_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AgentRunStatus] = mapped_column(
        SAEnum(AgentRunStatus, native_enum=False),
        nullable=False,
        default=AgentRunStatus.running,
    )
    answer_status: Mapped[AnswerStatus] = mapped_column(
        SAEnum(AnswerStatus, native_enum=False),
        nullable=False,
        default=AnswerStatus.none,
    )
    answer_blocks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    tool_trace: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(
        JSON, nullable=False, default=list
    )
    usage: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    round_trips: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utc_now)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    engagement: Mapped[Engagement] = relationship(back_populates="agent_runs")
