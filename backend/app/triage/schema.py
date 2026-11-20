"""Pydantic schemas for Support Triage pipeline, tools, and API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.triage.prompts import ALLOWED_PLACEHOLDERS

AllowedChannel = Literal["email", "chat", "web_form", "whatsapp"]
PriorityLevel = Literal["low", "medium", "high"]
ProposalDecision = Literal["approve", "reject"]


class ClassificationSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal: str
    source_quote: str = Field(default="", max_length=200)
    quote_verified: bool | None = None


class ClassificationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    secondary_category: str | None = None
    signals: list[ClassificationSignal] = Field(default_factory=list)
    rationale: str = Field(default="", max_length=300)


class ReviewFlag(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    where: str


class DraftOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reply_text: str = Field(..., max_length=1200)
    policy_refs: list[str] = Field(default_factory=list)
    reviewer_note: str | None = Field(default=None, max_length=300)


class CreateProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str | None = Field(default=None, max_length=200)
    body: str = Field(..., min_length=5, max_length=4000)
    channel: AllowedChannel = "web_form"


class ProposalFinalValues(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    priority: PriorityLevel
    queue: str
    reply_text: str = Field(..., min_length=1, max_length=2000)
    edited_fields: list[str] = Field(default_factory=list)


class ProposalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: ProposalDecision
    final: ProposalFinalValues | None = None
    reason: str | None = Field(default=None, max_length=300)


class ProposalDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: int
    decision: ProposalDecision
    status: str
    edited: bool
    edited_fields: list[str] = Field(default_factory=list)
    unresolved_placeholders: list[str] = Field(default_factory=list)
    decided_by: str
    decided_at: datetime


class TriageProposalResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int
    engagement_id: int
    ticket_hash: str | None = None
    subject: str | None = None
    body: str
    channel: str | None = None
    category: str
    secondary_category: str | None = None
    priority: str
    queue: str
    escalation: bool = False
    rule_id: str | None = None
    rule_definition: str | None = None
    signals: list[dict[str, Any]] = Field(default_factory=list)
    rationale: str | None = None
    draft_reply: str = ""
    policy_refs: list[str] = Field(default_factory=list)
    reviewer_note: str | None = None
    flags: list[dict[str, Any]] = Field(default_factory=list)
    tool_trace: list[dict[str, Any]] = Field(default_factory=list)
    model: str | None = None
    usage: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    status: str
    final_values: dict[str, Any] | None = None
    decided_by: str | None = None
    decision_reason: str | None = None
    edited: bool = False
    created_at: datetime
    decided_at: datetime | None = None
    allowed_placeholders: list[str] = Field(default_factory=lambda: list(ALLOWED_PLACEHOLDERS))

    @classmethod
    def from_orm_model(cls, p: Any) -> TriageProposalResponse:
        status_val = p.status.value if hasattr(p.status, "value") else str(p.status)
        return cls(
            id=p.id,
            engagement_id=p.engagement_id,
            ticket_hash=p.ticket_hash,
            subject=p.subject,
            body=p.ticket_text,
            channel=p.channel,
            category=p.proposed_category,
            secondary_category=p.secondary_category,
            priority=p.proposed_priority,
            queue=p.proposed_queue,
            escalation=p.escalation or False,
            rule_id=p.rule_fired,
            rule_definition=p.reasoning,
            signals=list(p.signals or []),
            rationale=p.rationale or p.reasoning,
            draft_reply=p.draft_reply or "",
            policy_refs=list(p.policy_refs or []),
            reviewer_note=p.reviewer_note,
            flags=list(p.flags or []),
            tool_trace=list(p.tool_trace or []),
            model=p.model,
            usage=p.usage,
            error=p.error,
            status=status_val,
            final_values=p.final_values,
            decided_by=p.decided_by,
            decision_reason=p.decision_reason,
            edited=p.edited or False,
            created_at=p.created_at,
            decided_at=p.decided_at,
        )


class ProposalCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal: TriageProposalResponse
    duplicate: bool = False


class ProposalsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[TriageProposalResponse]
    total: int
    page: int
    page_size: int
